#!/usr/bin/env bash
set -euo pipefail

ACTION="list"
REPOS="all"
ENGINE="${CONTAINER_ENGINE:-podman}"
LOCAL_TAG="local"
PUBLISH_TAG=""
REFRESH_IMAGES=false
DESTROY_DATA=false

usage() {
  cat <<'EOF'
Usage: multi-repo-workflow.sh [options]

  --action build|refresh|deploy|publish|reset-data|list
  --repos all|core-api,core-frontend,...
  --engine podman|docker
  --local-tag TAG
  --publish-tag TAG
  --refresh-images
  --destroy-data
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --action) ACTION="${2:?Missing value for --action}"; shift 2 ;;
    --repos) REPOS="${2:?Missing value for --repos}"; shift 2 ;;
    --engine) ENGINE="${2:?Missing value for --engine}"; shift 2 ;;
    --local-tag) LOCAL_TAG="${2:?Missing value for --local-tag}"; shift 2 ;;
    --publish-tag) PUBLISH_TAG="${2:?Missing value for --publish-tag}"; shift 2 ;;
    --refresh-images) REFRESH_IMAGES=true; shift ;;
    --destroy-data) DESTROY_DATA=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$ACTION" in
  build|refresh|deploy|publish|reset-data|list) ;;
  *) echo "Unknown action: $ACTION" >&2; exit 2 ;;
esac

case "$ENGINE" in
  podman|docker) ;;
  *) echo "Engine must be podman or docker." >&2; exit 2 ;;
esac

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PROJECTS_ROOT="$(cd -- "$ROOT/.." && pwd)"
SUITE_PATH="$ROOT/myai-suite"
ALL_IDS=(core-api core-frontend studio-frontend council-frontend aide-api aide-frontend knowledger-frontend)

label_for() {
  case "$1" in
    core-api) echo "Core API" ;;
    core-frontend) echo "Core Frontend" ;;
    studio-frontend) echo "Studio Frontend" ;;
    council-frontend) echo "Council Frontend" ;;
    aide-api) echo "MyAIDE API" ;;
    aide-frontend) echo "MyAIDE Frontend" ;;
    knowledger-frontend) echo "KnowLedger Frontend" ;;
  esac
}

path_for() {
  case "$1" in
    core-api) echo "$ROOT/backend" ;;
    core-frontend) echo "$ROOT/frontend" ;;
    studio-frontend) echo "$PROJECTS_ROOT/kairos-studio" ;;
    council-frontend) echo "$PROJECTS_ROOT/kairos-council" ;;
    aide-api) echo "$PROJECTS_ROOT/MyAIDE/src/MyAIDE.Api" ;;
    aide-frontend) echo "$PROJECTS_ROOT/MyAIDE/src/MyAIDE.Web" ;;
    knowledger-frontend) echo "$PROJECTS_ROOT/MyAI-KnowLedger" ;;
  esac
}

context_for() {
  case "$1" in
    core-api) echo "$ROOT/backend" ;;
    core-frontend) echo "$ROOT/frontend" ;;
    studio-frontend) echo "$PROJECTS_ROOT/kairos-studio" ;;
    council-frontend) echo "$PROJECTS_ROOT/kairos-council" ;;
    aide-api|aide-frontend) echo "$PROJECTS_ROOT/MyAIDE" ;;
    knowledger-frontend) echo "$PROJECTS_ROOT/MyAI-KnowLedger" ;;
  esac
}

dockerfile_for() {
  case "$1" in
    core-api) echo "$ROOT/backend/Dockerfile" ;;
    core-frontend) echo "$ROOT/frontend/Dockerfile" ;;
    studio-frontend) echo "$PROJECTS_ROOT/kairos-studio/Dockerfile" ;;
    council-frontend) echo "$PROJECTS_ROOT/kairos-council/Dockerfile" ;;
    aide-api) echo "$PROJECTS_ROOT/MyAIDE/src/MyAIDE.Api/Dockerfile" ;;
    aide-frontend) echo "$PROJECTS_ROOT/MyAIDE/src/MyAIDE.Web/Dockerfile" ;;
    knowledger-frontend) echo "$PROJECTS_ROOT/MyAI-KnowLedger/Dockerfile" ;;
  esac
}

image_for() {
  case "$1" in
    core-api) echo "myaitech/core-api" ;;
    core-frontend) echo "myaitech/core-frontend" ;;
    studio-frontend) echo "myaitech/studio" ;;
    council-frontend) echo "myaitech/council" ;;
    aide-api) echo "myaitech/aide-api" ;;
    aide-frontend) echo "myaitech/aide-frontend" ;;
    knowledger-frontend) echo "myaitech/knowledger" ;;
  esac
}

profile_for() {
  case "$1" in
    core-api|core-frontend) echo "core" ;;
    studio-frontend|council-frontend) echo "suite" ;;
    aide-api|aide-frontend) echo "de" ;;
    knowledger-frontend) echo "knowledger" ;;
  esac
}

is_known_id() {
  local requested="$1" id
  for id in "${ALL_IDS[@]}"; do
    [[ "$id" == "$requested" ]] && return 0
  done
  return 1
}

if [[ "$REPOS" == "all" ]]; then
  TARGETS=("${ALL_IDS[@]}")
else
  IFS=',' read -r -a TARGETS <<< "$REPOS"
  for index in "${!TARGETS[@]}"; do
    TARGETS[$index]="${TARGETS[$index]//[[:space:]]/}"
    if ! is_known_id "${TARGETS[$index]}"; then
      echo "Unknown repo id: ${TARGETS[$index]}" >&2
      exit 2
    fi
  done
fi

require_suite() {
  [[ -d "$SUITE_PATH" ]] || { echo "Suite path not found: $SUITE_PATH" >&2; exit 1; }
}

case "$ACTION" in
  list)
    printf '%-22s %-22s %-36s %s\n' ID LABEL IMAGE PATH
    for id in "${ALL_IDS[@]}"; do
      printf '%-22s %-22s %-36s %s\n' "$id" "$(label_for "$id")" "$(image_for "$id")" "$(path_for "$id")"
    done
    ;;
  build)
    for id in "${TARGETS[@]}"; do
      context="$(context_for "$id")"
      dockerfile="$(dockerfile_for "$id")"
      tag="$(image_for "$id"):$LOCAL_TAG"
      [[ -d "$context" ]] || { echo "Context not found: $context" >&2; exit 1; }
      [[ -f "$dockerfile" ]] || { echo "Dockerfile not found: $dockerfile" >&2; exit 1; }
      echo "[$id] building $tag from $context"
      "$ENGINE" build -f "$dockerfile" -t "$tag" "$context"
    done
    ;;
  refresh)
    require_suite
    declare -A images_by_profile=()
    for id in "${TARGETS[@]}"; do
      profile="$(profile_for "$id")"
      image="$(image_for "$id"):$LOCAL_TAG"
      if [[ -n "${images_by_profile[$profile]:-}" ]]; then
        images_by_profile[$profile]+=",$image"
      else
        images_by_profile[$profile]="$image"
      fi
    done
    for profile in core suite de knowledger; do
      [[ -n "${images_by_profile[$profile]:-}" ]] || continue
      echo "[suite:$profile] refreshing images ${images_by_profile[$profile]}"
      (cd "$SUITE_PATH" && CONTAINER_ENGINE="$ENGINE" bash ./refresh-images.sh "${images_by_profile[$profile]}" "$profile")
    done
    ;;
  deploy|reset-data)
    require_suite
    declare -A selected_profiles=()
    for id in "${TARGETS[@]}"; do selected_profiles["$(profile_for "$id")"]=1; done
    if [[ ${#selected_profiles[@]} -gt 1 ]]; then profile_set="all"; else profile_set="${!selected_profiles[*]}"; fi
    if [[ "$ACTION" == "reset-data" || "$DESTROY_DATA" == true ]]; then
      echo "[suite:$profile_set] destroying volumes and containers"
      (cd "$SUITE_PATH" && "$ENGINE" compose --profile "$profile_set" down -v)
    fi
    deploy_args=("$profile_set")
    [[ "$REFRESH_IMAGES" == true ]] && deploy_args+=(true)
    (cd "$SUITE_PATH" && CONTAINER_ENGINE="$ENGINE" bash ./deploy.sh "${deploy_args[@]}")
    ;;
  publish)
    [[ -n "$PUBLISH_TAG" ]] || { echo "--publish-tag is required for publish." >&2; exit 2; }
    for id in "${TARGETS[@]}"; do
      source="$(image_for "$id"):$LOCAL_TAG"
      destination="$(image_for "$id"):$PUBLISH_TAG"
      echo "[$id] tagging $source -> $destination"
      "$ENGINE" tag "$source" "$destination"
      echo "[$id] pushing $destination"
      "$ENGINE" push "$destination"
    done
    ;;
esac
