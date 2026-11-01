# The herdr panes' environment, loaded by ~/.zshrc only in a herdr pane (HERDR_PANE_ID): Claude Code in fullscreen
# mode (the input bar always at the bottom), herdr-fold's pbcopy first (formatted copies from answers) and the starship
# prompt in the theme's colors. Other terminals, and Claude in VS Code, are unchanged.
export CLAUDE_CODE_NO_FLICKER=1
case ":$PATH:" in
  *":$HOME/.config/herdr-fold/bin:"*) ;;
  *) export PATH="$HOME/.config/herdr-fold/bin:$PATH" ;;
esac
command -v starship >/dev/null 2>&1 && eval "$(starship init zsh)"
