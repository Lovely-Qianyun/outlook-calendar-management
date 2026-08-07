#!/bin/bash
# 真实账户边界条件回归：64 项行为断言（英文输出版，与 drill.sh 一一对应）
# 前置：已用 outlook_setup.py 对专用测试账户完成认证（token 在 ~/.outlook_cal_token.json）
# 用法：bash tests/drill-en.sh
set -u
cd "$(dirname "$0")/../.." || exit 1
PY="python scripts/outlook_cal.py"
export PYTHONIOENCODING=utf-8
export OCAL_LANG=en
PASS=0; FAIL=0
has() { echo "$1" | grep -q "$2"; }
chk() { if [ "$1" = "ok" ]; then PASS=$((PASS+1)); echo "  ✔ $2"; else FAIL=$((FAIL+1)); echo "  ✘ $2"; fi; }
c()  { chk "$(has "$1" "$2" && echo ok || echo no)" "$3"; }

echo "══════ 0. 基线清理 ══════"
for id in $($PY list --past 400 --days 400 | sed -n 's/^    🆔 \([^ ]*\)$/\1/p'); do $PY delete "$id" -y > /dev/null 2>&1; done
# 系列主事件单独清
python - <<'EOF'
import sys
sys.path.insert(0, 'scripts')
from ocal_auth import get_token
from ocal_graph import _call
from ocal_errors import CalError
from urllib.parse import quote
try:
    token = get_token()
    out = _call("GET", "/me/events?$select=id,subject,recurrence&$top=200", token, prefer_immutable=True)
    for e in out.get('value', []):
        if e.get('recurrence'):
            _call("DELETE", f"/me/events/{quote(e['id'], safe='')}", token, prefer_immutable=True)
            print("清 master:", e['subject'])
    print("基线清理完成")
except CalError as e:
    print("基线:", e)
EOF

echo "══════ 1. 时间解析边界 ══════"
OUT=$($PY add "边-补零小时" "2026-08-17 9:00" 2>&1); c "$OUT" "✅ Added to calendar:" "小时不补零 9:00 可解析"
OUT=$($PY add "边-非补零月" "2026-8-17 09:00" 2>&1); c "$OUT" "✅" "月份不补零 8-17 可解析"
OUT=$($PY add "边-24点" "2026-08-17 24:00" 2>&1); c "$OUT" "❌" "24:00 报错"
OUT=$($PY add "边-2月30" "2026-02-30" 2>&1); c "$OUT" "❌" "2月30日 报错"
OUT=$($PY add "边-无效月" "2026-13-01" 2>&1); c "$OUT" "❌" "13月 报错"
OUT=$($PY add "边-日期缺位" "2026-08-1" 2>&1); c "$OUT" "✅" "缺位日期 可解析(宽松)"
OUT=$($PY add "边-空白" "" 2>&1); c "$OUT" "❌" "空时间 报错"
OUT=$($PY add "边-乱码时间" "下周三下午" 2>&1); c "$OUT" "❌" "自然语言时间 报错(需规范格式)"
OUT=$($PY add "边-all-day带时间" "2026-08-17 09:00" --all-day 2>&1); c "$OUT" "❌" "--all-day 带时间报错"
OUT=$($PY add "边-end小于start" "2026-08-17 10:00" "2026-08-17 09:00" 2>&1); c "$OUT" "End time must be after" "end<start 报错"
OUT=$($PY add "边-等时" "2026-08-17 10:00" "2026-08-17 10:00" 2>&1); c "$OUT" "End time must be after" "end==start 报错"

echo "══════ 2. remind 边界 ══════"
OUT=$($PY add "边-remind0" "2026-08-17 09:00" --remind 0 --force 2>&1); c "$OUT" "✅" "--remind 0 允许(开始即提醒)"
OUT=$($PY add "边-remind负" "2026-08-17 09:00" --remind -1 2>&1); c "$OUT" "Reminder time cannot be negative" "--remind -1 报错"
OUT=$($PY add "边-全天remind超" "2026-08-17" --all-day --remind 2000 2>&1); c "$OUT" "supports at most 1826 days" "全天提醒超上限报错"

echo "══════ 3. 重复规则边界 ══════"
OUT=$($PY add "边-每0天" "2026-08-17 09:00" --repeat "每0天" --repeat-times 2 2>&1); c "$OUT" "❌" "每0天 报错或友好处理"
OUT=$($PY add "边-每周无日" "2026-08-17 09:00" --repeat "每周" --repeat-times 2 2>&1); c "$OUT" "✅" "每周(缺日)默认从起始日"
OUT=$($PY add "边-每3周" "2026-08-17 09:00" --repeat "每3周" --repeat-times 2 2>&1); c "$OUT" "✅" "每3周 默认起始日"
OUT=$($PY add "边-每月32日" "2026-08-17 09:00" --repeat "每月32日" 2>&1); c "$OUT" "❌" "每月32日 报错"
OUT=$($PY add "边-每月0日" "2026-08-17 09:00" --repeat "每月0日" 2>&1); c "$OUT" "❌" "每月0日 报错"
OUT=$($PY add "边-第5个" "2026-08-17 09:00" --repeat "每月第5个周三" 2>&1); c "$OUT" "❌" "每月第5个周X 报错"
OUT=$($PY add "边-13月" "2026-08-17 09:00" --repeat "每年13月1日" 2>&1); c "$OUT" "❌" "每年13月 报错"
OUT=$($PY add "边-次0" "2026-08-17 09:00" --repeat "每天" --repeat-times 0 2>&1); c "$OUT" "❌" "--repeat-times 0 报错"
OUT=$($PY add "边-次负" "2026-08-17 09:00" --repeat "每天" --repeat-times -1 2>&1); c "$OUT" "❌" "--repeat-times 负 报错"
OUT=$($PY add "边-until格式" "2026-08-17 09:00" --repeat "每天" --repeat-until "2026/08/31" 2>&1); c "$OUT" "❌" "--repeat-until 格式错 报错"
OUT=$($PY add "边-until早于" "2026-08-17 09:00" --repeat "每天" --repeat-until "2026-08-01" 2>&1); c "$OUT" "is before start date" "--repeat-until 早于开始 友好报错"
OUT=$($PY add "边-until不配合repeat" "2026-08-17 09:00" --repeat-until "2026-08-31" 2>&1); c "$OUT" "❌" "repeat-until 无 --repeat 报错"

echo "══════ 4. 冲突检测边界 ══════"
# 已有：边-remind0 在 08/17 09:00-10:00
OUT=$($PY add "边-重叠" "2026-08-17 09:30" "2026-08-17 10:30" 2>&1); c "$OUT" "⚠️" "重叠被警告"
OUT=$($PY add "边-相接不重叠" "2026-08-17 10:00" "2026-08-17 11:00" 2>&1); c "$OUT" "✅ Added to calendar:" "相接(10:00起)不警告"
$PY add "边-自由时段不算占用" "2026-08-17 11:00" "2026-08-17 12:00" --busy free --force > /dev/null 2>&1
OUT=$($PY add "边-与free重叠" "2026-08-17 11:30" "2026-08-17 12:30" 2>&1); c "$OUT" "✅ Added to calendar:" "与 showAs=free 重叠不警告"
$PY add "边-全天占用" "2026-08-18" --all-day --force > /dev/null 2>&1
OUT=$($PY add "边-全天vs时段" "2026-08-18 14:00" "2026-08-18 15:00" 2>&1); c "$OUT" "⚠️" "时段与全天重叠被警告"

echo "══════ 5. update 边界 ══════"
ID=$($PY list --search "边-remind0" --days 30 | sed -n 's/^    🆔 \([^ ]*\)$/\1/p' | head -1)
OUT=$($PY update "$ID" 2>&1); c "$OUT" "Nothing to update" "无字段 update 提示"
OUT=$($PY update "$ID" --subject "" -y 2>&1); c "$OUT" "✅ Updated:" "--subject \"\" 清空标题"
OUT=$($PY update "$ID" --location "" -y 2>&1); c "$OUT" "✅" "-l \"\" 清空地点"
OUT=$($PY update "$ID" --start "2026-08-17 10:30" -y 2>&1); c "$OUT" "End time must be after" "update 只给start且晚于原end 报错"
OUT=$($PY update "$ID" --start "2026-08-17 08:00" --end "2026-08-17 07:00" -y 2>&1); c "$OUT" "End time must be after" "update end<start 报错"
OUT=$($PY update "$ID" --all-day --start "2026-08-17 09:00" 2>&1); c "$OUT" "❌" "update 转全天带时间 报错"
OUT=$($PY update "不存在ID" --subject x -y 2>&1); c "$OUT" "❌" "update 不存在ID 友好报错"
OUT=$($PY update "$ID" --remind 100 -y 2>&1); c "$OUT" "✅" "update --remind 设提醒"

echo "══════ 6. 删除边界 ══════"
OUT=$($PY delete "不存在ID" -y 2>&1); c "$OUT" "❌" "delete 不存在ID 友好报错"
REALID=$($PY list --search "边-全天占用" --days 30 | sed -n 's/^    🆔 \([^ ]*\)$/\1/p' | head -1)
OUT=$($PY delete "$REALID" < /dev/null 2>&1); c "$OUT" "Cancelled" "delete 非交互EOF取消"

echo "══════ 7. 定期系列深度 ══════"
SID=$($PY add "深-每月一次" "2026-08-15 10:00" --repeat "每月15日" --repeat-times 3 --force | sed -n 's/^   🆔 \(.*\)$/\1/p')
OCC=$($PY list --search "深-每月一次" --days 365 | sed -n 's/^    🆔 \([^ ]*\)$/\1/p' | head -1)
OUT=$($PY read "$OCC"); c "$OUT" "occurrence #1" "月度系列第N次计算"
OUT=$($PY update "$OCC" --subject "深-例外" -y 2>&1); c "$OUT" "✅" "修改单次出现创建例外"
OUT=$($PY list --search "深-例外" --days 365); c "$OUT" "🔁(modified)" "例外在 list 标记"
OUT=$($PY next "$SID"); c "$OUT" "Next occurrence" "next master 可用"
OUT=$($PY next "$OCC"); c "$OUT" "Next occurrence" "next exception occurrence 可用"
OUT=$($PY next "不存在ID" 2>&1); c "$OUT" "❌" "next 不存在ID 报错"
# 非定期 next
NID=$($PY add "深-单次" "2026-08-25 09:00" --force | sed -n 's/^   🆔 \(.*\)$/\1/p')
OUT=$($PY next "$NID" 2>&1); c "$OUT" "not recurring" "next 非定期 报错"
# 例外删除（仅删本次）→ 系列其余保留
printf "1\ny\n" | $PY delete "$OCC" > /dev/null 2>&1
OUT=$($PY list --search "深-每月一次" --days 365); c "$OUT" "🔁(series)" "删例外后系列其余保留"
# 删整系列（master 确认路径，含整系列警告）
OUT=$(printf "y\n" | $PY delete "$SID" 2>&1); c "$OUT" "whole recurring series" "删整系列(master+警告+确认)"
OUT=$($PY list --search "深-每月一次" --days 365); c "$OUT" "no match" "删整系列后无残留"

echo "══════ 8. free/命令边界 ══════"
OUT=$($PY free "2026-08-17" --from "25:00" 2>&1); c "$OUT" "❌" "free --from 非法格式 报错"
OUT=$($PY free "2026-08-17" --from "18:00" --to "09:00" 2>&1); c "$OUT" "❌" "free --to<--from 报错"
OUT=$($PY free "2026-08-17" --days 0 2>&1); c "$OUT" "❌" "free --days 0 报错"
OUT=$($PY free "2026-13-01" 2>&1); c "$OUT" "❌" "free 非法日期 报错"
OUT=$($PY free "2026-08-17" --from 09:00 --to 18:00 2>&1); c "$OUT" "free" "free 正常输出"
OUT=$($PY free --days 3 2>&1 | wc -l | xargs -I{} echo "行数:{}"); echo "   (≥3 行=每天一行)"

echo "══════ 9. --json 边界 ══════"
OUT=$($PY --json list --days 1 2>/dev/null | python -c "import json,sys; d=json.load(sys.stdin); print(len(d)>=0)"); c "$OUT" "True" "--json list 可解析"
OUT=$($PY --json add "边-json事件" "2026-08-26 09:00" 2>/dev/null | python -c "import json,sys; d=json.load(sys.stdin); print(d['subject'])"); c "$OUT" "边-json事件" "--json add 输出 result"
OUT=$($PY --json delete "不存在" 2>/dev/null | python -c "import json,sys; d=json.load(sys.stdin); print('error' in d)"); c "$OUT" "True" "--json 错误路径结构化"
ERR=$($PY add "边-错误stderr" "坏时间" 2>&1 >/dev/null); chk "$(echo "$ERR" | grep -q "❌" && echo ok || echo no)" "非 --json 错误走 stderr"

echo "══════ 10. 其他边界 ══════"
OUT=$($PY add "边-emoji标题🎉" "2026-08-27 09:00" --force 2>&1); c "$OUT" "✅" "emoji 标题"
LONG=$(python -c "print('字'*500)")
OUT=$($PY add "边-长备注" "2026-08-27 10:00" -b "$LONG" --force 2>&1); c "$OUT" "✅" "500字长备注"
OUT=$($PY add "边-多类别" "2026-08-27 11:00" --category "A,B,C" --force 2>&1); c "$OUT" "🏷️ \['A', 'B', 'C'\]" "多类别逗号分隔"
OUT=$($PY add "边-importance非法" "2026-08-27 12:00" --importance 超级高 2>&1); c "$OUT" "invalid choice" "非法重要度 argparse 拒绝"
OUT=$($PY add "边-日期乱序" "2026-08-27 09:00" "2026-08-26 10:00" 2>&1); c "$OUT" "End time must be after" "跨天乱序时间 报错"

echo ""
echo "══════ 结果: $PASS 通过, $FAIL 失败 ══════"
