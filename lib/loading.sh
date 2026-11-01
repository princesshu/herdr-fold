# The installer's loading animation (loaded by lib/common.sh): during a long, silent step, sheep walk across the
# terminal jumping fences, in the theme's colors (theme_colors). Half-block pixel art: a cell holds two pixels (▀ in
# the upper one's color on the lower one's background).

# The sheep, 4 × 3 pixels in solid colors, facing right (they walk left to right, like a progress bar): W wool,
# F face (the head low in front), L legs (two, under the body); a blank pixel row on top, so they stand on the grass
SHEEP_ART=(
  "...."
  ".WW."
  "WWWF"
  "L.L."
)
# Over a fence the same sheep a pixel higher (on a row higher too): a pixel of air between its legs and the fence
SHEEP_UP=("${SHEEP_ART[@]:1}" "${SHEEP_ART[0]//?/.}")
SHEEP_WIDTH=4 SHEEP_HEIGHT=2                      # in character cells: two pixels make one cell, one above the other
# The colors are terminal color codes: 5;N for one of the 256, 2;R;G;B for a theme's own.
# The palettes (W F L): light sheep and dark sheep take turns — face and legs light enough to show on a dark background
SHEEP_PALETTES=("5;231 5;245 5;245" "5;239 5;244 5;250")
SHEEP_COUNT=4                                     # sheep in the window, light and dark in turn (fewer if too narrow)
# The fences: posts a row high, standing on the grass (layout places them)
FENCE_COLOR="5;94"
FENCE_ROW=$'\033[0;38;'"$FENCE_COLOR"$'m█\033[0m'
# The grass: a thin strip under the feet (the upper half of a row), one solid dark green
GRASS_COLOR="5;22"
# The theme's colors, from the theme setter (src/themes/apply.py): wool, face, wool, face, fence, grass
LOADING_COLORS="${HOME:-}/.local/state/herdr-fold/loading-colors.txt"

# theme_colors — the sheep, the fences and the grass in the theme's colors; left as they are without the file, or with
# one the theme setter did not write
theme_colors() {
  local colors=() color code='^2;[0-9]{1,3};[0-9]{1,3};[0-9]{1,3}$'
  [ -f "$LOADING_COLORS" ] || return 0
  read -r -a colors < "$LOADING_COLORS" || true
  [ "${#colors[@]}" -eq 6 ] || return 0
  for color in "${colors[@]}"; do [[ $color =~ $code ]] || return 0; done
  SHEEP_PALETTES=("${colors[0]} ${colors[1]} ${colors[1]}" "${colors[2]} ${colors[3]} ${colors[3]}")
  FENCE_COLOR=${colors[4]} GRASS_COLOR=${colors[5]}
  FENCE_ROW=$'\033[0;38;'"$FENCE_COLOR"$'m█\033[0m'
}

# render_sheep N "W F L" — puts sheep N's rows (SHEEP_HEIGHT of them) into SPRITE[N * SHEEP_HEIGHT + row], and the
# same sheep a pixel higher (SHEEP_UP) into SPRITE_UP
render_sheep() {
  local n=$1 r=0 line
  while IFS= read -r line; do SPRITE[n * SHEEP_HEIGHT + r]=$line; r=$((r + 1)); done \
    < <(render_rows "$2" "${SHEEP_ART[@]}")
  r=0
  while IFS= read -r line; do SPRITE_UP[n * SHEEP_HEIGHT + r]=$line; r=$((r + 1)); done \
    < <(render_rows "$2" "${SHEEP_UP[@]}")
}
# render_rows "W F L" PIXELROW… — the pixel rows in half blocks, two a line (the upper one's color on the lower one's)
render_rows() {
  local colors=($1) art=("${@:2}") r c top bottom ct cb line
  for ((r = 0; r < ${#art[@]}; r += 2)); do
    line=
    for ((c = 0; c < SHEEP_WIDTH; c++)); do
      top=${art[r]:c:1}; bottom=${art[r + 1]:c:1}
      ct=$(pixel_color "$top"); cb=$(pixel_color "$bottom")
      if [ -z "$ct" ] && [ -z "$cb" ]; then line+=$'\033[0m '
      elif [ -z "$cb" ]; then line+=$'\033[0;38;'"$ct"'m▀'
      elif [ -z "$ct" ]; then line+=$'\033[0;38;'"$cb"'m▄'
      elif [ "$ct" = "$cb" ]; then line+=$'\033[0;38;'"$ct"'m█'
      else line+=$'\033[0;38;'"$ct"';48;'"$cb"'m▀'; fi
    done
    printf '%s\n' "$line"$'\033[0m'
  done
}
pixel_color() {
  case $1 in
    W) echo "${colors[0]}" ;; F) echo "${colors[1]}" ;; L) echo "${colors[2]}" ;;
  esac
}

# lift_at X — true if the sheep at column X is over a fence (from a column before it to a column after it): then it is
# up (a row and a pixel), so it never shares a cell with the fence; false on the grass
lift_at() {
  local f
  for f in "${FENCES[@]}"; do [ "$f" -ge $(($1 - 1)) ] && [ "$f" -le $(($1 + SHEEP_WIDTH)) ] && return 0; done
  return 1
}

# scene T — sets ROWS (the sky row, then the sheep's rows; the fences stand on the last one) for step T: FLOCK sheep
# SHEEP_SPACING apart on a looping track, jumping the fences. ITEM is keyed by row * 1000 + column, as bash lists the
# keys in order: a row is built left to right.
scene() {
  local t=$1 k n x top i key r col done_to=()
  ITEM=(); ITEM_WIDTH=(); ROWS=(); UP=()
  for ((r = 0; r <= SHEEP_HEIGHT; r++)); do ROWS[r]=; done_to[r]=0; done
  for col in "${FENCES[@]}"; do
    ITEM[SHEEP_HEIGHT * 1000 + col]=$FENCE_ROW; ITEM_WIDTH[SHEEP_HEIGHT * 1000 + col]=1
  done
  for ((k = 0; k < FLOCK; k++)); do
    n=$(( t / SHEEP_SPACING - k )); x=$(( t % SHEEP_SPACING + k * SHEEP_SPACING ))
    top=1
    if lift_at "$x"; then top=0; UP[k]=$((n % 2)); fi             # the light ones (0) or the dark ones (1)
    for ((i = 0; i < SHEEP_HEIGHT; i++)); do
      key=$(( (top + i) * 1000 + x ))
      if [ $top = 0 ]; then ITEM[key]=${SPRITE_UP[(n % 2) * SHEEP_HEIGHT + i]}
      else ITEM[key]=${SPRITE[(n % 2) * SHEEP_HEIGHT + i]}; fi
      ITEM_WIDTH[key]=$SHEEP_WIDTH
    done
  done
  for key in "${!ITEM[@]}"; do
    r=$((key / 1000)); col=$((key % 1000))
    ROWS[r]+="${SPACES:0:$((col - done_to[r]))}${ITEM[key]}"; done_to[r]=$((col + ITEM_WIDTH[key]))
  done
}

# layout WIDTH — sets FLOCK (fewer than SHEEP_COUNT in a narrow window), SHEEP_SPACING and FENCES for WIDTH columns.
# The sheep are an odd number of half gaps apart, so the light ones jump while the dark ones land, then the other way
# round; fences are at least two jumps apart (a jump: the sheep's width + 2 columns).
layout() {
  local m=0 gap col jump=$((SHEEP_WIDTH + 2))
  FLOCK=$SHEEP_COUNT
  while SHEEP_SPACING=$(( ($1 - SHEEP_WIDTH + 1) / FLOCK )); [ "$SHEEP_SPACING" -lt "$jump" ] && [ "$FLOCK" -gt 2 ]; do
    FLOCK=$((FLOCK - 1))
  done
  while [ $(( 2 * SHEEP_SPACING / (2 * m + 3) )) -ge $((2 * jump)) ]; do m=$((m + 1)); done
  gap=$(( 2 * SHEEP_SPACING / (2 * m + 1) / 2 * 2 ))                  # even: half a gap is a whole number of columns
  SHEEP_SPACING=$(( (2 * m + 1) * gap / 2 ))
  FENCES=()
  for ((col = gap / 2; col < FLOCK * SHEEP_SPACING + SHEEP_WIDTH - 3; col += gap)); do FENCES+=("$col"); done
}

# loading "Message" COMMAND [ARG…] — runs COMMAND: after LOADING_AFTER seconds a line (mark, message, time), after
# LOADING_SHEEP the sheep, then kept LOADING_SHEEP_MIN seconds so they never flash (LOADING_PLAIN: the line only). The
# line COMMAND writes to LOADING_PHASE follows the message. Then COMMAND's output and status; no terminal: just runs.
LOADING_AFTER=${LOADING_AFTER:-1}
LOADING_SHEEP=${LOADING_SHEEP:-8}
LOADING_SHEEP_MIN=${LOADING_SHEEP_MIN:-3}
LOADING_MARKS=(⠖ ⠲ ⠴ ⠦)              # a gap turning in a 2×2 of braille dots, the middle rows: inside the brackets
LOADING_TURN=30                       # hundredths of a second a quarter turn takes: a calm turn in 1.2 s
loading() {
  local msg=$1; shift
  if ! interactive || [ "${TERM:-dumb}" = dumb ]; then "$@"; return; fi
  local out pid rc rows=0 width t start=$SECONDS secs frame r c grass= tenths=0 sheep= line shown mark LOADING_PHASE
  out=$(mktemp); LOADING_PHASE=$(mktemp)
  export LOADING_PHASE                                                     # to COMMAND only: the local ends with it
  "$@" > "$out" 2>&1 < /dev/null &
  pid=$!
  trap 'kill $pid 2>/dev/null; [ $rows -gt 0 ] && loading_clear $rows; rm -f "$out" "$LOADING_PHASE"; exit 130' INT TERM
  while kill -0 "$pid" 2>/dev/null && [ $tenths -lt $((LOADING_AFTER * 10)) ]; do
    sleep 0.1; tenths=$((tenths + 1))
  done
  if kill -0 "$pid" 2>/dev/null; then
    width=$(( $(tput cols 2>/dev/null || echo 80) - 2 ))
    [ -z "${LOADING_PLAIN:-}" ] && [ "$width" -ge 30 ] && sheep=1
    rows=1
    printf '\033[?25l' > /dev/tty
    for ((t = 0; ; t++)); do                                             # the line, until the sheep's turn
      kill -0 "$pid" 2>/dev/null || break
      [ -n "$sheep" ] && [ $tenths -ge $((LOADING_SHEEP * 10)) ] && break
      secs=$(( SECONDS - start ))
      loading_text $((width - 12)); mark=${MARK_BUSY/…/${LOADING_MARKS[t * 10 / LOADING_TURN % 4]}}
      printf '\r  %s %s %d:%02d\033[K' "$mark" "$line" $((secs / 60)) $((secs % 60)) > /dev/tty
      sleep 0.1; tenths=$((tenths + 1))
    done
    if [ -n "$sheep" ] && kill -0 "$pid" 2>/dev/null; then
      printf '\r\033[K' > /dev/tty                                      # the line goes: the scene starts there
      rows=$((SHEEP_HEIGHT + 4))
      printf -v SPACES '%*s' "$width" ''
      layout "$width"
      theme_colors
      for ((c = 0; c < width; c++)); do grass+='▀'; done
      grass=$'\033[38;'"$GRASS_COLOR"'m'"$grass"$'\033[0m'
      render_sheep 0 "${SHEEP_PALETTES[0]}"; render_sheep 1 "${SHEEP_PALETTES[1]}"
      printf '%*s' $((rows - 1)) '' | tr ' ' '\n' > /dev/tty               # room for the scene
      t=$((FLOCK * SHEEP_SPACING))                                         # the flock already fills the row
      for ((shown = 0; ; shown++)); do                                     # a frame every 0.12 s
        kill -0 "$pid" 2>/dev/null || [ $((shown * 12)) -lt $((LOADING_SHEEP_MIN * 100)) ] || break
        scene "$t"
        secs=$(( SECONDS - start ))
        loading_text $((width - 12)); mark=${MARK_BUSY/…/${LOADING_MARKS[shown * 12 / LOADING_TURN % 4]}}
        printf -v frame '\r\033[%dA\033[K\n' $((rows - 1))              # the blank row
        for ((r = 0; r <= SHEEP_HEIGHT; r++)); do frame+="${ROWS[r]}"$'\033[K\n'; done
        printf '%s%s\033[K\n  %s %s %d:%02d\033[K' "$frame" "$grass" "$mark" "$line" $((secs / 60)) $((secs % 60)) \
          > /dev/tty
        t=$((t + 1))
        sleep 0.12
      done
    fi
    loading_clear $rows
  fi
  wait "$pid"; rc=$?
  trap - INT TERM
  cat "$out"; rm -f "$out" "$LOADING_PHASE"
  return $rc
}

# loading_phase TEXT — for a step under loading: what it is doing now, shown after the message; nothing outside one
loading_phase() { [ -z "${LOADING_PHASE:-}" ] || printf '%s\n' "$1" > "$LOADING_PHASE"; }

# loading_text MAX — LINE: the message, then what the step last wrote into LOADING_PHASE (no control characters: a
# remote machine's words may be in it), cut to MAX characters
loading_text() {
  local phase=
  read -r phase < "$LOADING_PHASE" || true                                  # empty until the step writes
  phase=${phase//[[:cntrl:]]/}
  line=$msg${phase:+ · $phase}
  [ "${#line}" -le "$1" ] || line="${line:0:$(($1 - 1))}…"
}

# loading_clear ROWS — clears the scene, puts the cursor back at its first line and shows it again
loading_clear() {
  local r
  printf '\r\033[K' > /dev/tty
  for ((r = 1; r < $1; r++)); do printf '\033[1A\r\033[K' > /dev/tty; done
  printf '\033[?25h' > /dev/tty
}
