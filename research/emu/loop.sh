#!/bin/bash
# حلقة تحكم بالمحاكي عن بُعد عبر git (بحث مؤقت).
# cmd.txt: السطر الأول "seq N"، ثم أوامر: tap X Y | swipe X1 Y1 X2 Y2 MS | wait S | shot NAME | back | launch | stop
set -u
BR=claude/quirky-ride-r4oor0
OUT=research/emu/out
PKG=com.grandgames.magicsort
mkdir -p "$OUT"
git config user.name "emu-session-bot"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

log() { echo "[$(date +%T)] $*" | tee -a "$OUT/log.txt"; }

shot() {
  adb exec-out screencap -p > /tmp/s.png 2>/dev/null || return 0
  python3 - "$OUT/$1.jpg" <<'PY' || true
import sys
from PIL import Image
im = Image.open('/tmp/s.png').convert('RGB')
w, h = im.size
s = 1000 / h
im.resize((int(w * s), 1000), Image.LANCZOS).save(sys.argv[1], quality=82)
PY
}

publish() {
  git add -A "$OUT"
  git commit -qm "محاكي: $1" || return 0
  for i in 1 2 3 4 5 6; do
    if git pull -q --rebase origin "$BR" && git push -q origin "HEAD:$BR"; then return 0; fi
    sleep 4
  done
  log "فشل الرفع"
}

log "الشاشة: $(adb shell wm size | tr -d '\r') كثافة: $(adb shell wm density | tr -d '\r') ABI: $(adb shell getprop ro.product.cpu.abilist | tr -d '\r')"
cd /tmp/game && adb install-multiple -r -g com.grandgames.magicsort.apk config.armeabi_v7a.apk 2>&1 | tail -2 | tee -a "$GITHUB_WORKSPACE/$OUT/log.txt"
cd "$GITHUB_WORKSPACE"
adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
log "شُغّلت اللعبة"

# لقطات تلقائية أثناء التحميل الأول
for t in 10 20 30 45 60 90 120; do
  sleep 10
  shot "000_launch_${t}s"
  [ "$t" = 30 ] && publish "لقطات التحميل الأولى"
done
echo "done 0" > "$OUT/state.txt"
publish "لقطات التحميل"

last=0
idle_since=$(date +%s)
while true; do
  git fetch -q origin "$BR" || { sleep 5; continue; }
  cmds=$(git show FETCH_HEAD:research/emu/cmd.txt 2>/dev/null || true)
  seq=$(echo "$cmds" | awk 'NR==1 && $1=="seq" {print $2}')
  if [ -n "$seq" ] && [ "$seq" -gt "$last" ]; then
    log "تنفيذ الدفعة $seq"
    stop=0
    while read -r -u 3 a b c d e f; do
      case "$a" in
        tap)    adb shell input tap "$b" "$c" ;;
        swipe)  adb shell input swipe "$b" "$c" "$d" "$e" "${f:-300}" ;;
        wait)   sleep "$b" ;;
        shot)   shot "$(printf '%03d' "$seq")_$b" ;;
        back)   adb shell input keyevent 4 ;;
        launch) adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1 ;;
        stop)   stop=1 ;;
      esac
    done 3< <(echo "$cmds" | tail -n +2)
    shot "$(printf '%03d' "$seq")_end"
    echo "done $seq" > "$OUT/state.txt"
    publish "الدفعة $seq"
    last=$seq
    idle_since=$(date +%s)
    [ "$stop" = 1 ] && { log "انتهت الجلسة"; publish "نهاية"; exit 0; }
  fi
  if [ $(( $(date +%s) - idle_since )) -gt 2400 ]; then
    log "لا أوامر منذ 40 دقيقة، إنهاء"
    publish "نهاية بسبب الخمول"
    exit 0
  fi
  sleep 6
done
