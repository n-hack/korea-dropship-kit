#!/bin/bash
# せどりの部品を全部検算する（道具を直したら毎回これを回す・ネットに出ない・お金は動かない）
cd "$(dirname "$0")" || exit 1
bad=0
for f in kc cs coupang watch orders pace abiz shoko waku title_ko jisseki urekata gazou kanzei_ok shiire haniro run; do
  out=$(python3 "$f.py" --selftest 2>&1); rc=$?
  last=$(printf '%s\n' "$out" | tail -1)
  printf '%-8s rc=%s %s\n' "$f" "$rc" "$last"
  [ "$rc" = 0 ] || bad=$((bad+1))
done
out=$(python3 e2e_test.py 2>&1); rc=$?
printf '%-8s rc=%s %s\n' "e2e" "$rc" "$(printf '%s\n' "$out" | tail -1)"
[ "$rc" = 0 ] || bad=$((bad+1))
echo "落ちた部品 ${bad}本"
exit $bad
