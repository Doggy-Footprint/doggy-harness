# Paths come from this file's own directory, never from the work tree's top level: git can run a hook
# of one checkout with the current directory in another (git worktree add), whose commit lacks these files.
harness_git_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

harness_dispatch() {
  local name="$1"
  shift
  local common_dir local_hook private_hook stdin_file="" status=0
  common_dir="$(git rev-parse --git-common-dir)"
  local_hook="$harness_git_dir/../local/git/$name"
  private_hook="$common_dir/hooks/$name"

  local run_local=0 run_private=0
  if [ -f "$local_hook" ]; then
    if [ -x "$local_hook" ]; then
      run_local=1
    else
      echo "$name: .harness/local/git/$name is not executable; run chmod +x .harness/local/git/$name" >&2
    fi
  fi
  if [ -f "$private_hook" ] && [ -x "$private_hook" ]; then
    run_private=1
  fi

  # Hooks such as pre-push and post-rewrite read stdin, and a pipe can be read once: with two
  # hooks to run, both get the bytes from a temporary file. A terminal is never read.
  if [ "$run_local" = 1 ] && [ "$run_private" = 1 ] && [ ! -t 0 ]; then
    stdin_file="$(mktemp)"
    trap 'rm -f "$stdin_file"' EXIT
    cat > "$stdin_file"
  fi

  if [ "$run_local" = 1 ]; then
    if [ -n "$stdin_file" ]; then
      "$local_hook" "$@" < "$stdin_file" || status=$?
    else
      "$local_hook" "$@" || status=$?
    fi
    if [ "$status" -ne 0 ]; then
      exit "$status"
    fi
  fi

  if [ "$run_private" = 1 ]; then
    if [ -n "$stdin_file" ]; then
      "$private_hook" "$@" < "$stdin_file" || status=$?
    else
      "$private_hook" "$@" || status=$?
    fi
    exit "$status"
  fi
  exit 0
}
