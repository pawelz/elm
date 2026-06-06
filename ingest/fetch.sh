#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Help / Usage message
show_help() {
    echo "Usage: $0 --good <good_maildirs> --bad <bad_maildirs> --remote <remote_path>"
    echo ""
    echo "Flags:"
    echo "  --good     Comma-separated list of good Maildir directories relative to Maildir/"
    echo "  --bad      Comma-separated list of bad Maildir directories relative to Maildir/"
    echo "  --remote   Remote path in format username@host:path_to_maildir_base"
    echo "  -h, --help Show this help message"
}

GOOD_LIST=""
BAD_LIST=""
REMOTE=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --good)
            GOOD_LIST="$2"
            shift 2
            ;;
        --bad)
            BAD_LIST="$2"
            shift 2
            ;;
        --remote)
            REMOTE="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Error: Unknown argument $1" >&2
            show_help
            exit 1
            ;;
        esac
done

# Validate inputs
if [ -z "$GOOD_LIST" ] && [ -z "$BAD_LIST" ]; then
    echo "Error: At least one of --good or --bad must be specified." >&2
    exit 1
fi

if [ -z "$REMOTE" ]; then
    echo "Error: --remote must be specified." >&2
    exit 1
fi

# 1. Determine local target directory name with disambiguation character
CHARACTERS="0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
DATE=$(date +"%Y%m%d")
SELECTED_CHAR=""

for (( i=0; i<${#CHARACTERS}; i++ )); do
    CHAR="${CHARACTERS:$i:1}"
    DIR_NAME="data/${DATE}-${CHAR}"
    if [ ! -d "$DIR_NAME" ]; then
        SELECTED_CHAR="$CHAR"
        break
    fi
done

if [ -z "$SELECTED_CHAR" ]; then
    echo "Error: Ran out of disambiguation characters (0-9, a-z, A-Z) for date ${DATE}." >&2
    exit 1
fi

TARGET_DIR="data/${DATE}-${SELECTED_CHAR}"

# 2. Create target subdirectories
mkdir -p "$TARGET_DIR/good"
mkdir -p "$TARGET_DIR/bad"

# 3. Create inputs.txt debug file
cat <<EOF > "$TARGET_DIR/inputs.txt"
good: $GOOD_LIST
bad: $BAD_LIST
EOF

# Create a temporary directory for flattening structures
TEMP_DIR=$(mktemp -d "${TARGET_DIR}/.tmp.XXXXXX")

# 4. Copy good Maildirs (only cur and new subdirectories)
IFS=',' read -ra GOOD_DIRS <<< "$GOOD_LIST"
for dir in "${GOOD_DIRS[@]}"; do
    if [ -n "$dir" ]; then
        echo "good:$dir"
        rsync -rt --quiet --include="*/" --include="cur/**" --include="new/**" --exclude="*" "${REMOTE}/${dir}/" "$TEMP_DIR/"
    fi
done

# Flatten good emails directly to the flat good/ directory
if [ -d "$TEMP_DIR" ] && [ "$(ls -A "$TEMP_DIR")" ]; then
    find "$TEMP_DIR" -type f -exec mv {} "$TARGET_DIR/good/" \;
    rm -rf "$TEMP_DIR"/*
fi

# 5. Copy bad Maildirs (only cur and new subdirectories)
IFS=',' read -ra BAD_DIRS <<< "$BAD_LIST"
for dir in "${BAD_DIRS[@]}"; do
    if [ -n "$dir" ]; then
        echo "bad:$dir"
        rsync -rt --quiet --include="*/" --include="cur/**" --include="new/**" --exclude="*" "${REMOTE}/${dir}/" "$TEMP_DIR/"
    fi
done

# Flatten bad emails directly to the flat bad/ directory
if [ -d "$TEMP_DIR" ] && [ "$(ls -A "$TEMP_DIR")" ]; then
    find "$TEMP_DIR" -type f -exec mv {} "$TARGET_DIR/bad/" \;
fi

# Clean up temp directory
rm -rf "$TEMP_DIR"

exit 0
