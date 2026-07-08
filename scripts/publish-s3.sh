#!/usr/bin/env bash
# Publish a human-html artifact to an S3 bucket you own and print an open URL.
#
# Entirely optional: the skill never uploads anything unless you run this
# script yourself. Why it exists: human-html artifacts are shared with readers
# as a URL, NOT as a file attachment (chat/preview surfaces run no JS; see
# SKILL.md Rule 9). If you have an S3 bucket, this handles the upload and
# returns a link that renders in the browser.
#
# Usage:
#   publish-s3.sh <local-html-file> [key]
#     <local-html-file>  path to the .html artifact
#     [key]              optional S3 object key (default: the file's basename)
#
# Config (env):
#   HUMAN_HTML_S3_BUCKET   REQUIRED: the bucket to upload to (bring your own)
#   HUMAN_HTML_S3_REGION   optional: bucket region; unset = aws CLI config/profile decides
#   HUMAN_HTML_S3_PREFIX   optional key prefix, e.g. "reviews/"
#   HUMAN_HTML_S3_EXPIRES  optional presign lifetime in seconds (default 604800)
#
# Exit codes: 0 ok · 1 bucket not configured · 2 usage · 3 AWS not authenticated · 4 bucket unreachable · 5 upload failed
set -euo pipefail

BUCKET="${HUMAN_HTML_S3_BUCKET:-}"
REGION="${HUMAN_HTML_S3_REGION:-}"
PREFIX="${HUMAN_HTML_S3_PREFIX:-}"

if [[ -z "$BUCKET" ]]; then
  cat >&2 <<'EOF'
HUMAN_HTML_S3_BUCKET is not set; nothing was uploaded.
This helper is optional and publishes to an S3 bucket YOU own:
  export HUMAN_HTML_S3_BUCKET=your-bucket-name
Optional: HUMAN_HTML_S3_REGION, HUMAN_HTML_S3_PREFIX, HUMAN_HTML_S3_EXPIRES (presign seconds).
See references/patterns.md "Sharing & hosting" for setup details.
EOF
  exit 1
fi

# Pass --region only when explicitly configured; otherwise the aws CLI
# config/profile decides. The ${arr[@]+...} expansion keeps bash 3.2 (macOS)
# happy under set -u when the array is empty.
region_args=()
[[ -n "$REGION" ]] && region_args=(--region "$REGION")

file="${1:-}"
if [[ -z "$file" || ! -f "$file" ]]; then
  echo "usage: publish-s3.sh <local-html-file> [key]" >&2
  exit 2
fi

# 0) Keep a durable LOCAL copy under THIS session's docs/human-html/ lane and upload FROM there, so
#    every artifact that reaches S3 also lives in the project you run from, not a sibling workspace.
#    Resolve the lane without nesting when already inside one; never silently clobber a same-named file.
case "$PWD" in
  */docs/human-html)   lane="$PWD" ;;
  */docs/human-html/*) lane="${PWD%%/docs/human-html/*}/docs/human-html" ;;
  *)
    lane="$PWD/docs/human-html"
    # Mirror human_html_artifacts.py resolve_create_root: if an ANCESTOR already has a
    # lane, creating one here forks the gallery. Warn (don't relocate: the session cwd wins).
    anc="${PWD%/*}"
    while [[ -n "$anc" ]]; do
      if [[ -d "$anc/docs/human-html" ]]; then
        echo "Note: an existing docs/human-html lane is at $anc (an ancestor of $PWD); the durable copy here forks the gallery. Run from $anc to reuse it." >&2
        break
      fi
      [[ "$anc" == */* ]] || break
      anc="${anc%/*}"
    done
    ;;
esac
base="$(basename "$file")"
abs="$(cd "$(dirname "$file")" && pwd)/$base"
case "$abs" in
  "$lane"/*) file="$abs" ;;                          # already in the lane; use in place
  *)
    mkdir -p "$lane"
    dest="$lane/$base"
    if [[ -e "$dest" ]] && ! cmp -s "$file" "$dest"; then
      echo "Refusing to overwrite $dest: a different artifact with the same name already exists. Rename and re-run." >&2
      exit 2
    fi
    cp "$file" "$dest"
    file="$dest"
    echo "Stored durable local copy at $file." >&2
    ;;
esac
# The lane is validated by human_html_artifacts.py; warn if this name won't pass the file contract.
if ! printf '%s' "$base" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z]+-[a-z0-9-]+\.html$'; then
  echo "Note: '$base' isn't a YYYY-MM-DD-kind-slug.html name; human_html_artifacts.py check will flag it in this lane." >&2
fi
key="${2:-$(basename "$file")}"
[[ -n "$PREFIX" ]] && key="${PREFIX%/}/$key"

# 1) AWS auth must be active on this machine.
if ! aws sts get-caller-identity >/dev/null 2>&1; then
  cat >&2 <<EOF
AWS is not authenticated on this machine.
The artifact stays local: $file
Authenticate (e.g. 'aws sso login' or set your credentials/profile), then re-run:
  $0 "$file" "$key"
EOF
  exit 3
fi

# 2) Bucket must exist and be reachable. This script never creates buckets.
head_err="$(aws s3api head-bucket --bucket "$BUCKET" ${region_args[@]+"${region_args[@]}"} 2>&1)" || head_rc=$?
if [[ -n "${head_rc:-}" ]]; then
  if   printf '%s' "$head_err" | grep -q 404; then why="does not exist (404): create it, or set HUMAN_HTML_S3_BUCKET to the correct name.";
  elif printf '%s' "$head_err" | grep -q 403; then why="exists but this identity has no access (403): check your AWS profile/permissions.";
  else why="is not reachable: check the name/region and your AWS session."; fi
  echo "Bucket s3://$BUCKET $why" >&2
  echo "The artifact stays local: $file" >&2
  exit 4
fi

# 3) Upload as text/html so the browser renders it inline (not a download).
if ! aws s3 cp "$file" "s3://$BUCKET/$key" \
      --content-type "text/html; charset=utf-8" \
      ${region_args[@]+"${region_args[@]}"} >/dev/null; then
  echo "upload failed: s3://$BUCKET/$key" >&2
  exit 5
fi

# 4) Return an OPEN URL the reader can click and have render in the browser.
#    Public bucket / static-website hosting -> the clean direct URL renders as-is.
#    Private bucket -> a presigned URL (the same kind the console "Open" button makes);
#    the object was uploaded as text/html so it renders inline rather than downloading.
if [[ -n "$REGION" ]]; then
  obj_url="https://${BUCKET}.s3.${REGION}.amazonaws.com/${key}"
else
  obj_url="https://${BUCKET}.s3.amazonaws.com/${key}"
fi
code="$(curl -s -o /dev/null -m 10 -w '%{http_code}' "$obj_url" 2>/dev/null || echo 000)"
if [[ "$code" == "200" ]]; then
  echo "$obj_url"
else
  exp="${HUMAN_HTML_S3_EXPIRES:-604800}"   # request 7 days; capped by session for temp creds
  presigned="$(aws s3 presign "s3://${BUCKET}/${key}" --expires-in "$exp" ${region_args[@]+"${region_args[@]}"} 2>/dev/null || true)"
  if [[ -z "$presigned" ]]; then
    echo "uploaded, but presign failed for s3://${BUCKET}/${key}" >&2
    exit 5
  fi
  if [[ "$presigned" == *X-Amz-Security-Token* ]]; then
    echo "Private bucket: returning a presigned OPEN URL. NOTE: your AWS creds are temporary (SSO/STS), so this link stays valid only until your session token expires (well under the requested ${exp}s), not permanently. For a durable link, enable static-website hosting on the bucket or put CloudFront in front of it." >&2
  else
    echo "Private bucket: returning a presigned OPEN URL, valid ~${exp}s." >&2
  fi
  echo "$presigned"
fi
