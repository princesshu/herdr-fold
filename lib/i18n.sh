# The texts: $CATALOG_DIR/<HERDR_FOLD_LANG>.txt (default and fallback en.txt), one `key = text` per line; a line ending
# in \ goes on in the next, indented one. Set CATALOG_DIR (the package's lang folder, or the one that came with the
# prepare script), then source this file.

# t KEY [ARG…] — prints the text of KEY (no newline at the end; use it as "$(t KEY …)"): %s takes the next ARG,
# %% is a percent sign, \n a new line; anything else, backslashes too, is printed as it is
t() {
  local file="$CATALOG_DIR/${HERDR_FOLD_LANG:-en}.txt"
  [ -f "$file" ] || file="$CATALOG_DIR/en.txt"
  awk -- '
    BEGIN { key = ARGV[1] " = "; for (i = 2; i < ARGC; i++) arg[i - 1] = ARGV[i]; ARGC = 1 }   # the file: stdin
    { sub(/\r$/, "") }
    index($0, key) == 1 {
      text = substr($0, length(key) + 1); out = ""; n = 0
      while (text ~ /\\$/ && (getline more) > 0) {                # goes on in the next line, without its indentation
        sub(/\r$/, "", more); sub(/^[ \t]+/, "", more)
        text = substr(text, 1, length(text) - 1) more
      }
      while (match(text, /%s|%%|\\n/)) {
        m = substr(text, RSTART, RLENGTH)
        out = out substr(text, 1, RSTART - 1) (m == "%s" ? arg[++n] : (m == "%%" ? "%" : "\n"))
        text = substr(text, RSTART + RLENGTH)
      }
      printf "%s", out text; exit
    }' "$@" < "$file"
}
