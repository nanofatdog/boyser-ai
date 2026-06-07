# bash/zsh completion for boyser-ai
# Install: source this file from ~/.bashrc or ~/.zshrc
# Or: sudo cp completion.sh /etc/bash_completion.d/boyser-ai

_boyser_ai_completions() {
    local cur prev words cword
    if type _init_completion &>/dev/null; then
        _init_completion
    else
        COMPREPLY=()
        cur="${COMP_WORDS[COMP_CWORD]}"
        prev="${COMP_WORDS[COMP_CWORD-1]}"
    fi

    # Find repo for --model completion
    local repo_dir
    if command -v boyser-ai &>/dev/null; then
        repo_dir="$(dirname "$(readlink -f "$(command -v boyser-ai)")")"
    fi

    case "$prev" in
        --model|-m)
            # Suggest common model names
            COMPREPLY=($(compgen -W "claude-sonnet-4-6 claude-haiku-4-5 qwen3-coder-tools qwen3.5-coder-tools deepseek-v4 deepseek-r1 gemma4 glm4-9b llama3.3-70b" -- "$cur"))
            return
            ;;
        --local)
            # Suggest URLs
            COMPREPLY=($(compgen -W "http://localhost:8080/v1 http://localhost:11434/v1" -- "$cur"))
            return
            ;;
    esac

    # Main flags
    COMPREPLY=($(compgen -W "--help --version --setup --yolo --local --model -V" -- "$cur"))
}

# Register for both bash and zsh
if [[ -n "$ZSH_VERSION" ]]; then
    compdef _boyser_ai_completions boyser-ai
elif [[ -n "$BASH_VERSION" ]]; then
    complete -F _boyser_ai_completions boyser-ai
fi
