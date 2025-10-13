#!/bin/bash
# Pre-commit hook to block unwanted .md files
# Only allow: README.md, CHANGELOG.md, ROADMAP.md

ALLOWED_MD_FILES=("README.md" "CHANGELOG.md" "ROADMAP.md")

# Get list of staged .md files
STAGED_MD_FILES=$(git diff --cached --name-only --diff-filter=A | grep '\.md$')

if [ -n "$STAGED_MD_FILES" ]; then
    BLOCKED_FILES=""
    
    for file in $STAGED_MD_FILES; do
        BASENAME=$(basename "$file")
        IS_ALLOWED=false
        
        for allowed in "${ALLOWED_MD_FILES[@]}"; do
            if [ "$BASENAME" = "$allowed" ]; then
                IS_ALLOWED=true
                break
            fi
        done
        
        if [ "$IS_ALLOWED" = false ]; then
            BLOCKED_FILES="$BLOCKED_FILES\n  - $file"
        fi
    done
    
    if [ -n "$BLOCKED_FILES" ]; then
        echo "❌ Error: Attempting to commit unwanted .md files!"
        echo "Only these .md files are allowed: ${ALLOWED_MD_FILES[*]}"
        echo ""
        echo "Blocked files:$BLOCKED_FILES"
        echo ""
        echo "Please remove these files or update the whitelist in scripts/pre-commit-hook.sh"
        exit 1
    fi
fi

exit 0

