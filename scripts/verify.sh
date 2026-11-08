#!/usr/bin/env bash
# Token-cheap, composable, hierarchical verification runner. Prints ONE line; details live in files.
#   scripts/verify.sh                        full: lint, smoke, unit, integration, system, perf, stress, torture, security
#   scripts/verify.sh --quick                fast gate: lint, smoke, unit
#   scripts/verify.sh --tier t1,t2           run all stages in comma-separated tiers (e.g. smoke,unit or perf,stress,torture)
#   scripts/verify.sh --only s1 [s2...]      cherry-pick specific stages (see --list)
#   scripts/verify.sh --match PATTERN        cherry-pick test case/function name pattern (combine with --only or --tier)
#   scripts/verify.sh --failed               re-run only stages that failed last run
#   scripts/verify.sh --list                 list stage<TAB>tier inventory
#   scripts/verify.sh --status               print last one-line result (no run)
#   scripts/verify.sh --report               print markdown report from last run
# Result tree (target/verify/):
#   STATUS            PASS | FAIL            (read this first)
#   summary.tsv       stage<TAB>tier<TAB>PASS|FAIL<TAB>secs   (read on FAIL)
#   report.md         human-readable hierarchical report
#   junit.xml         JUnit XML summary for CI / test tooling
#   <stage>/status    PASS|FAIL   <stage>/fail.txt  compact failure excerpt (<=40 lines)
#   <stage>/log       full output (read only if fail.txt is not enough)
# Exit code: 0 all pass, 1 any fail, 2 usage.
set -uo pipefail
cd "$(dirname "$0")/.."
OUT=target/verify
mkdir -p "$OUT"
[ -d .venv/bin ] && export PATH="$PWD/.venv/bin:$PATH"
PYTHON_BIN="${PYTHON:-$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo python3)}"

TIERS=(lint smoke unit integration system perf stress torture security)

# Emit "stage<TAB>tier" pairs. Auto-discovers tests/<tier>/* and top-level tests/*.
all_stages() {
  echo -e "lint\tlint"
  if [ -f Cargo.toml ]; then
    echo -e "unit\tunit"
  fi
  local t f b
  for t in smoke unit integration system perf stress torture security; do
    if [ -d "tests/$t" ]; then
      for f in "tests/$t"/test_*.py "tests/$t"/*_test.py "tests/$t"/*.rs "tests/$t"/*.test.ts "tests/$t"/*.test.js "tests/$t"/*.bats; do
        [ -e "$f" ] || continue
        b=$(basename "$f"); b="${b%.*}"
        echo -e "${t}:${b}\t${t}"
      done
    fi
  done
  for f in tests/*.rs tests/test_*.py tests/*.bats; do
    [ -e "$f" ] || continue
    b=$(basename "$f"); b="${b%.*}"
    echo -e "integration:${b}\tintegration"
  done
}

stage_tier() {
  all_stages | awk -F'\t' -v s="$1" '$1==s{print $2; exit}'
}

cmd_for() {
  local s="$1" m="${2:-}"
  local tier="${s%%:*}" name="${s#*:}"
  if [ -f Cargo.toml ]; then
    case "$s" in
      fmt)    echo "cargo fmt --check" ;;
      lint)   echo "cargo clippy -q --all-targets -- -D warnings" ;;
      unit)   echo "cargo test -q --lib --bins ${m:+-- $m} --no-fail-fast" ;;
      *:*)    echo "cargo test -q --test $name ${m:+-- $m} --no-fail-fast" ;;
      *)      return 1 ;;
    esac
  elif [ -f pyproject.toml ] || [ -d tests ]; then
    case "$s" in
      lint)   echo "ruff check . 2>/dev/null || $PYTHON_BIN -m py_compile src/**/*.py 2>/dev/null || true" ;;
      unit)   echo "pytest -q -rs tests/unit ${m:+-k $m}" ;;
      *:*)
        local target
        target=$(ls "tests/$tier/$name".* "tests/$name".* 2>/dev/null | head -n1)
        [ -n "$target" ] || return 1
        echo "pytest -q -rs \"$target\" ${m:+-k $m}" ;;
      *)      return 1 ;;
    esac
  else
    return 1
  fi
}

line() {
  [ -f "$OUT/summary.tsv" ] || { echo "NORUN"; return; }
  local n p f secs
  n=$(wc -l <"$OUT/summary.tsv"); f=$(grep -c $'\tFAIL\t' "$OUT/summary.tsv"); p=$((n-f))
  secs=$(awk -F'\t' '{s+=$4} END{print s+0}' "$OUT/summary.tsv")
  if [ "$f" -eq 0 ]; then echo "PASS $p/$n ${secs}s"
  else echo "FAIL $f/$n: $(awk -F'\t' '$3=="FAIL"{printf "%s ",$1}' "$OUT/summary.tsv")-> $OUT/<stage>/fail.txt"; fi
}

write_reports() {
  [ -f "$OUT/summary.tsv" ] || return
  local status_line
  status_line=$(line)
  {
    echo "# Verification Report"
    echo ""
    echo "**Result:** \`$status_line\`"
    echo ""
    echo "| Stage | Tier | Status | Time (s) | Log / Failure Excerpt |"
    echo "|---|---|---|---|---|"
    awk -F'\t' -v out="$OUT" '{
      s = $1; gsub(/:/, "_", s)
      ref = ($3 == "FAIL") ? out "/" s "/fail.txt" : out "/" s "/log"
      printf "| `%s` | `%s` | **%s** | %ss | `%s` |\n", $1, $2, $3, $4, ref
    }' "$OUT/summary.tsv"
  } >"$OUT/report.md"

  local n f secs
  n=$(wc -l <"$OUT/summary.tsv"); f=$(grep -c $'\tFAIL\t' "$OUT/summary.tsv")
  secs=$(awk -F'\t' '{s+=$4} END{print s+0}' "$OUT/summary.tsv")
  {
    echo "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
    echo "<testsuites tests=\"$n\" failures=\"$f\" time=\"$secs\">"
    echo "  <testsuite name=\"verify\" tests=\"$n\" failures=\"$f\" time=\"$secs\">"
    while IFS=$'\t' read -r stg tr st sc; do
      echo "    <testcase name=\"$stg\" classname=\"$tr\" time=\"$sc\">"
      if [ "$st" = "FAIL" ]; then
        echo "      <failure message=\"stage $stg failed\"><![CDATA[$(cat "$OUT/${stg//:/_}/fail.txt" 2>/dev/null)]]></failure>"
      fi
      echo "    </testcase>"
    done <"$OUT/summary.tsv"
    echo "  </testsuite>"
    echo "</testsuites>"
  } >"$OUT/junit.xml"
}

mode=full; stages=(); tiers_csv=""; match_pat=""
while [ $# -gt 0 ]; do
  case "$1" in
    --quick)  mode=tier; tiers_csv="lint,smoke,unit"; shift ;;
    --tier)   mode=tier; tiers_csv="${2:-}"; shift 2 ;;
    --failed) mode=failed; shift ;;
    --list)   all_stages; exit 0 ;;
    --status) line; exit 0 ;;
    --report) [ -f "$OUT/report.md" ] && cat "$OUT/report.md" || line; exit 0 ;;
    --match)  match_pat="${2:-}"; shift 2 ;;
    --only)   mode=only; shift
              while [ $# -gt 0 ] && [[ "$1" != --* ]]; do stages+=("$1"); shift; done ;;
    *)        sed -n '2,18p' "$0"; exit 2 ;;
  esac
done

case $mode in
  full)
    while IFS= read -r line_stg; do [ -n "$line_stg" ] && stages+=("$line_stg"); done < <(all_stages | cut -f1) ;;
  tier)
    while IFS= read -r line_stg; do [ -n "$line_stg" ] && stages+=("$line_stg"); done < <(all_stages | awk -F'\t' -v tl=",$tiers_csv," 'index(tl, ","$2",")>0{print $1}') ;;
  failed)
    while IFS= read -r line_stg; do [ -n "$line_stg" ] && stages+=("$line_stg"); done < <(awk -F'\t' '$3=="FAIL"{print $1}' "$OUT/summary.tsv" 2>/dev/null)
    [ ${#stages[@]} -eq 0 ] && { echo "PASS nothing-failed"; exit 0; } ;;
esac

[ ${#stages[@]} -eq 0 ] && { echo "no stages matched (try --list)"; exit 2; }

new=$(mktemp)
for s in "${stages[@]}"; do
  c=$(cmd_for "$s" "$match_pat") || { echo "unknown stage: $s (try --list)"; rm -f "$new"; exit 2; }
  tr=$(stage_tier "$s"); [ -z "$tr" ] && tr="${s%%:*}"
  d="$OUT/${s//:/_}"; rm -rf "$d"; mkdir -p "$d"
  t0=$SECONDS
  if bash -c "$c" >"$d/log" 2>&1; then st=PASS; else st=FAIL; fi
  echo "$st" >"$d/status"
  if [ "$st" = FAIL ]; then
    { grep -E '^(error|warning|FAIL|FAILED|E   )(\[|:| )|panicked at|^test .* FAILED|^failures:|^--- FAIL:|^AssertionError' "$d/log" || tail -n 25 "$d/log"; } \
      | awk '!seen[$0]++' | head -40 >"$d/fail.txt"
  fi
  printf '%s\t%s\t%s\t%s\n' "$s" "$tr" "$st" $((SECONDS-t0)) >>"$new"
done

if [ "$mode" = full ] || [ ! -f "$OUT/summary.tsv" ]; then
  sort -u -k1,1 "$new" >"$OUT/summary.tsv"
else
  { grep -vFf <(printf '%s\t\n' "${stages[@]}") "$OUT/summary.tsv" 2>/dev/null || true; cat "$new"; } | sort -u -k1,1 >"$OUT/summary.tsv.tmp"
  mv "$OUT/summary.tsv.tmp" "$OUT/summary.tsv"
fi
rm -f "$new"
write_reports
r=$(line); echo "${r%% *}" >"$OUT/STATUS"; echo "$r"
[ "${r%% *}" = PASS ]
