#!/bin/bash
# 真实账户边界条件回归：106 项行为断言（英文输出版，与 drill.sh 一一对应）
# 前置：已用 outlook_setup.py 对专用测试账户完成认证（token 在 ~/.outlook_cal_token.json）
# 用法：bash tests/integration/drill-en.sh confirm <测试账户邮箱>
#       或 TEST_ACCOUNT=<测试账户邮箱> bash tests/integration/drill-en.sh confirm
# ⚠️ 危险：本脚本会删除测试账户 ±400 天窗口内的全部日程！只允许对专用测试账户运行。
# 防呆（双重锁）：① 必须显式传参 confirm；② 必须指定测试账户且与当前连接账户一致，否则拒绝执行。
set -u
if [ "${1:-}" != "confirm" ]; then
  echo "❌ 防呆保护：drill-en.sh 会删除测试账户 400 天内的所有日程，请确认目标账户是【专用测试账户】。"
  echo "   确认无误后请运行：bash tests/integration/drill-en.sh confirm <测试账户邮箱>"
  exit 2
fi
EXPECT_ACCOUNT="${2:-${TEST_ACCOUNT:-}}"
if [ -z "$EXPECT_ACCOUNT" ]; then
  echo "❌ 防呆保护：请显式指定测试账户邮箱（第二参数或 TEST_ACCOUNT 环境变量）。"
  exit 2
fi
cd "$(dirname "$0")/../.." || exit 1
PY="${PYTHON:-python} scripts/outlook_cal.py"
export PYTHONIOENCODING=utf-8
export OCAL_LANG=en
PASS=0; FAIL=0
has() { echo "$1" | grep -q "$2"; }
chk() { if [ "$1" = "ok" ]; then PASS=$((PASS+1)); echo "  ✔ $2"; else FAIL=$((FAIL+1)); echo "  ✘ $2"; fi; }
c()  { chk "$(has "$1" "$2" && echo ok || echo no)" "$3"; }

echo "══════ 0. 账户守卫 + 基线清理 ══════"
# 第二道锁：当前连接的账户必须与指定测试账户一致（防止 token 指向真实账户时被 confirm 一键清空）
CONNECTED=$($PY --json status 2>/dev/null | "${PYTHON:-python}" -c"import sys,json; d=json.load(sys.stdin); print((d.get('account') or '').lower())")
if [ "$(echo "$CONNECTED" | tr 'A-Z' 'a-z')" != "$(echo "$EXPECT_ACCOUNT" | tr 'A-Z' 'a-z')" ]; then
  echo "❌ 当前连接账户（$CONNECTED）与指定测试账户（$EXPECT_ACCOUNT）不一致，拒绝执行任何删除"
  exit 2
fi
echo "✅ 账户校验通过：$CONNECTED（专用测试账户）"
# 基线清理：先删全部系列主事件（一个 DELETE 消灭整个系列），再删剩余单次事件；
# 全程 _get_all 翻页，不设 $top 避免超 200 条时漏页
"${PYTHON:-python}" - <<'EOF'
import sys
sys.path.insert(0, 'scripts')
from ocal_auth import get_token
from ocal_graph import _call, _get_all
from ocal_errors import CalError
from urllib.parse import quote
try:
    token = get_token()
    events = _get_all("/me/events?$select=id,subject,recurrence", token, prefer_immutable=True)
    for e in events:
        if e.get('recurrence'):
            _call("DELETE", f"/me/events/{quote(e['id'], safe='')}", token, prefer_immutable=True)
            print("清系列:", e['subject'])
    for e in events:
        if not e.get('recurrence'):
            _call("DELETE", f"/me/events/{quote(e['id'], safe='')}", token, prefer_immutable=True)
            print("清单次:", e['subject'])
    print("基线清理完成")
except CalError as e:
    print("基线:", e)
EOF
OUT=$($PY list --past 400 --days 400 --summary); c "$OUT" "no matching events" "清理后 ±400 天窗口为空"

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
OUT=$($PY --json list --days 1 2>/dev/null | "${PYTHON:-python}" -c"import json,sys; d=json.load(sys.stdin); print(len(d)>=0)"); c "$OUT" "True" "--json list 可解析"
OUT=$($PY --json add "边-json事件" "2026-08-26 09:00" 2>/dev/null | "${PYTHON:-python}" -c"import json,sys; d=json.load(sys.stdin); print(d['subject'])"); c "$OUT" "边-json事件" "--json add 输出 result"
OUT=$($PY --json delete "不存在" 2>/dev/null | "${PYTHON:-python}" -c"import json,sys; d=json.load(sys.stdin); print('error' in d)"); c "$OUT" "True" "--json 错误路径结构化"
ERR=$($PY add "边-错误stderr" "坏时间" 2>&1 >/dev/null); chk "$(echo "$ERR" | grep -q "❌" && echo ok || echo no)" "非 --json 错误走 stderr"

echo "══════ 10. 其他边界 ══════"
OUT=$($PY add "边-emoji标题🎉" "2026-08-27 09:00" --force 2>&1); c "$OUT" "✅" "emoji 标题"
LONG=$("${PYTHON:-python}" -c "print('字'*500)")
OUT=$($PY add "边-长备注" "2026-08-27 10:00" -b "$LONG" --force 2>&1); c "$OUT" "✅" "500字长备注"
OUT=$($PY add "边-多类别" "2026-08-27 11:00" --category "A,B,C" --force 2>&1); c "$OUT" "🏷️ \['A', 'B', 'C'\]" "多类别逗号分隔"
OUT=$($PY add "边-importance非法" "2026-08-27 12:00" --importance 超级高 2>&1); c "$OUT" "invalid choice" "非法重要度 argparse 拒绝"
OUT=$($PY add "边-日期乱序" "2026-08-27 09:00" "2026-08-26 10:00" 2>&1); c "$OUT" "End time must be after" "跨天乱序时间 报错"

echo "══════ 11. move 专项 ══════"
MVID=$($PY add "移-待移" "2026-08-19 14:00" "2026-08-19 15:00" --force | sed -n 's/^   🆔 \(.*\)$/\1/p')
OUT=$($PY move "$MVID" --days 2 -y 2>&1); c "$OUT" "✅ Moved:" "move --days 平移"
OUT=$($PY read "$MVID"); c "$OUT" "08/21 14:00" "move --days 后时间正确"
OUT=$($PY move "$MVID" --to "2026-08-25" -y 2>&1); c "$OUT" "✅ Moved:" "move --to 移到指定日期"
OUT=$($PY read "$MVID"); c "$OUT" "08/25 14:00" "move --to 后时间正确"
OUT=$($PY move "$MVID" --days 0 -y 2>&1); c "$OUT" "Move days cannot be 0" "move 0 天报错"
OUT=$($PY move "$MVID" --days 1 --to "2026-08-26" -y 2>&1); c "$OUT" "cannot be used together" "move --days+--to 报错"
OUT=$($PY move "不存在ID" --days 1 -y 2>&1); c "$OUT" "❌" "move 不存在ID 报错"
MAID=$($PY add "移-全天" "2026-08-20" --all-day --force | sed -n 's/^   🆔 \(.*\)$/\1/p')
OUT=$($PY move "$MAID" --days 3 -y 2>&1); c "$OUT" "✅ Moved:" "move 全天平移"
OUT=$($PY read "$MAID"); c "$OUT" "08/23" "move 全天后日期正确"
MSID=$($PY add "移-系列" "2026-08-22 09:00" --repeat "每周六" --repeat-times 3 --force | sed -n 's/^   🆔 \(.*\)$/\1/p')
OUT=$($PY move "$MSID" --days 1 -y 2>&1); c "$OUT" "every occurrence" "move 系列主事件警告"
CSID=$($PY add "移-跨界" "2026-08-24 09:00" --repeat "每天" --repeat-times 2 --force | sed -n 's/^   🆔 \(.*\)$/\1/p')
COCC=$($PY list --search "移-跨界" --days 30 | sed -n 's/^    🆔 \([^ ]*\)$/\1/p' | head -1)
OUT=$($PY move "$COCC" --to "2026-08-25" -y 2>&1); c "$OUT" "adjacent occurrence" "move 例外跨相邻出现报错"

echo "══════ 12. 多天全天 / 快捷命令 / 筛选 ══════"
OUT=$($PY add "多-旅行" "2026-09-05" "2026-09-07" --all-day --force 2>&1); c "$OUT" "✅ Added to calendar:" "add 多天全天"
DID=$($PY list --search "多-旅行" --days 60 | sed -n 's/^    🆔 \([^ ]*\)$/\1/p' | head -1)
OUT=$($PY read "$DID"); c "$OUT" "09/05 - 09/07" "read 显示多天全天范围"
OUT=$($PY add "多-坏end" "2026-09-06" "2026-09-06 18:00" --all-day 2>&1); c "$OUT" "Invalid time format" "add 全天带时间 end 报错"
UID2=$($PY add "多-单天" "2026-09-08" --all-day --force | sed -n 's/^   🆔 \(.*\)$/\1/p')
OUT=$($PY update "$UID2" --start "2026-09-08" --end "2026-09-10" -y 2>&1); c "$OUT" "✅ Updated:" "update 改多天全天"
OUT=$($PY read "$UID2"); c "$OUT" "09/08 - 09/10" "update 后显示多天范围"
OUT=$($PY today --summary); c "$OUT" "📅\|✨" "today --summary 可用"
OUT=$($PY tomorrow); c "$OUT" "📅\|✨" "tomorrow 可用"
OUT=$($PY week --summary); c "$OUT" "📅\|✨" "week --summary 可用"
OUT=$($PY list --created-after "2026-08-01" --reminders 2>&1); c "$OUT" "📅\|✨" "--created-after+--reminders 组合可用"
OUT=$($PY add "多-私密" "2026-08-28 09:00" --private --importance 高 --force 2>&1); c "$OUT" "🔒 Private" "add --private 显示"
OUT=$($PY add "多-重要" "2026-08-28 10:00" --importance 高 --force 2>&1); c "$OUT" "⭐ Importance: high" "add --importance 显示"
$PY add "多-多天占" "2026-09-15" "2026-09-17" --all-day --force > /dev/null 2>&1
OUT=$($PY add "多-第2天重叠" "2026-09-16 14:00" "2026-09-16 15:00" 2>&1); c "$OUT" "⚠️" "多天全天第2天与时段冲突被警告"

echo "══════ 13. v1.2.0 行为回归 ══════"
RID=$($PY add "回-转时段" "2026-08-29" --all-day --force | sed -n 's/^   🆔 \(.*\)$/\1/p')
OUT=$($PY update "$RID" --no-all-day --start "2026-08-29 09:00" --end "2026-08-29 10:00" --remind 10 -y 2>&1); c "$OUT" "✅ Updated:" "update 全天转时段+remind"
OUT=$($PY --json read "$RID" 2>/dev/null | "${PYTHON:-python}" -c"import json,sys; d=json.load(sys.stdin); print(d.get('reminderMinutesBeforeStart'))"); c "$OUT" "10" "转时段后 remind 按分钟(10 而非 14400)"
FXID=$($PY add "回-取消" "2026-08-30 09:00" "2026-08-30 10:00" --repeat "每天" --repeat-times 2 --force | sed -n 's/^   🆔 \(.*\)$/\1/p')
FOCC=$($PY list --search "回-取消" --days 30 | sed -n 's/^    🆔 \([^ ]*\)$/\1/p' | head -1)
$PY delete "$FOCC" -y > /dev/null 2>&1
OUT=$($PY free "2026-08-30" --from 09:00 --to 18:00); c "$OUT" "free all day" "已取消单次不算占用(free)"
DXID=$($PY add "回-单次删" "2026-08-31 09:00" --force | sed -n 's/^   🆔 \(.*\)$/\1/p')
OUT=$($PY delete "$DXID" -y 2>&1); c "$OUT" 'Removed "回-单次删" from the calendar' "delete 单次日程中性文案"
QRID=$($PY add "回-解除" "2026-09-01 09:00" --repeat "每天" --repeat-times 3 --force | sed -n 's/^   🆔 \(.*\)$/\1/p')
OUT=$($PY update "$QRID" --repeat "" -y 2>&1); c "$OUT" "Recurrence removed" "update --repeat \"\" 解除定期"

echo "══════ 14. TZ 环境变量覆盖 ══════"
OUT=$(TZ=Asia/Hong_Kong $PY list --days 1 2>&1); c "$OUT" "📅\|✨" "TZ=Asia/Hong_Kong 映射到官方名并查询成功"
OUT=$(TZ=America/Phoenix $PY list --days 1 2>&1); c "$OUT" "📅\|✨" "TZ=America/Phoenix Windows 官方名被 Graph 接受"

echo "══════ 15. DST 切换日（TZ=America/New_York）══════"
OUT=$(TZ=America/New_York $PY add "夏-回拨" "2026-11-01 01:30" "2026-11-01 02:30" --force 2>&1); c "$OUT" "✅ Added to calendar:" "回拨日(11/01) 事件创建"
DID3=$(TZ=America/New_York $PY list --search "夏-回拨" --days 120 | sed -n 's/^    🆔 \([^ ]*\)$/\1/p' | head -1)
OUT=$(TZ=America/New_York $PY read "$DID3"); c "$OUT" "11/01 01:30" "回拨日事件读回时间正确"
OUT=$(TZ=America/New_York $PY add "夏-跳变" "2026-03-08 02:30" "2026-03-08 03:30" --force 2>&1); c "$OUT" "does not exist" "跳变日(03/08) 不存在的本地时间有警告"
OUT=$(TZ=America/New_York $PY free "2026-11-01" --from 09:00 --to 18:00 2>&1); c "$OUT" "free" "回拨日 free 可用"
OUT=$(TZ=America/New_York $PY list --from "2026-11-01" --days 1 2>&1); c "$OUT" "📅\|✨" "回拨日 list 可用"

echo "══════ 16. 邮箱时区对齐 ══════"
# 本机时区 = Eastern Standard Time（TZ 覆盖），邮箱首选时区由 Graph 返回；
# 全天日程必须按邮箱时区写入，不能跟随本机时区。
# 注意：不能用 --json read 校验——读请求带 Prefer 时区头，Graph 会把返回的
# timeZone 字段改写成请求时区；用不带 Prefer 的原始 GET 按 UTC 时刻核对。
OUT=$(TZ=America/New_York $PY status 2>&1); c "$OUT" "Mailbox timezone" "status 提示邮箱时区与本机不同"
AZID=$(TZ=America/New_York $PY add "邮-全天" "2026-09-20" --all-day --force | sed -n 's/^   🆔 \(.*\)$/\1/p')
OK=$("${PYTHON:-python}" - "$AZID" <<'PYEOF'
import sys, requests
sys.path.insert(0, 'scripts')
from ocal_auth import get_token
from ocal_graph import _call
from ocal_time import _resolve_tz
from datetime import datetime
tok = get_token()
mtz = _call("GET", "/me/mailboxSettings?$select=timeZone", tok).get("timeZone")
raw = requests.get("https://graph.microsoft.com/v1.0/me/events/" + sys.argv[1] + "?$select=start",
                   headers={"Authorization": "Bearer " + tok}, timeout=(10, 30)).json()
dt = datetime.fromisoformat(raw["start"]["dateTime"].replace("Z", "+00:00"))
day = dt.astimezone(_resolve_tz(mtz)).strftime("%Y-%m-%d")
print("ok" if day == "2026-09-20" else "no:" + day)
PYEOF
)
chk "$OK" "全天日程按邮箱时区写入（UTC 时刻核对）"

echo "══════ 17. 相对时间 ══════"
OUT=$($PY add "相-今天" "今天 09:00" "今天 10:00" --force 2>&1); c "$OUT" "✅ Added to calendar:" "add 今天(相对时间) 可用"
TODAY_OK=$($PY --json list --from "今天" --days 1 2>/dev/null | "${PYTHON:-python}" -c "import json,sys; print(any(e.get('subject')=='相-今天' for e in json.load(sys.stdin)))")
chk "$TODAY_OK" "今天创建的日程落在今天的列表"
OUT=$($PY add "相-明天" "明天 09:00" "明天 10:00" --force 2>&1); c "$OUT" "✅ Added to calendar:" "add 明天(相对时间) 可用"
TOM_OK=$($PY --json list --from "明天" --days 1 2>/dev/null | "${PYTHON:-python}" -c "import json,sys; print(any(e.get('subject')=='相-明天' for e in json.load(sys.stdin)))")
chk "$TOM_OK" "明天创建的日程落在明天的列表"

echo ""
echo "══════ 结果: $PASS 通过, $FAIL 失败 ══════"
