#!/usr/bin/env bash
# Deploy Amnesia to Cloud Run.
#
# One script, safe to re-run: every step checks for what already exists, so a
# failed run can be fixed and repeated rather than unwound. Source deploys are
# used instead of a local Docker build, because Cloud Build produces the same
# image on any machine and needs no local daemon.
set -euo pipefail

PROJECT="${GOOGLE_CLOUD_PROJECT:-}"
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
SERVICE="${AMNESIA_SERVICE:-amnesia}"
GCLOUD="${GCLOUD_BIN:-gcloud}"

if [ -z "$PROJECT" ]; then
  PROJECT="$($GCLOUD config get-value project 2>/dev/null || true)"
fi
if [ -z "$PROJECT" ] || [ "$PROJECT" = "(unset)" ]; then
  echo "ERROR: no project. Run: gcloud config set project YOUR_PROJECT" >&2
  exit 1
fi

echo "==> Project: $PROJECT"
echo "==> Region:  $REGION"
echo "==> Service: $SERVICE"

# ----------------------------------------------------------------- APIs
echo "==> Enabling APIs (idempotent, slow only the first time)"
$GCLOUD services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  firestore.googleapis.com \
  aiplatform.googleapis.com \
  cloudscheduler.googleapis.com \
  --project "$PROJECT"

# ------------------------------------------------------------- Firestore
# Firestore refuses a second database in the same project, and that error is
# expected on every run after the first. It is not a failure.
echo "==> Ensuring Firestore database"
$GCLOUD firestore databases create --location="$REGION" --project "$PROJECT" 2>/dev/null \
  || echo "    (already exists)"

# ------------------------------------------------------------------ key
# The Gemini key is passed as an env var rather than baked into the image, so
# rotating it does not mean rebuilding.
KEY_ARG=""
if [ -n "${GOOGLE_API_KEY:-}" ]; then
  KEY_ARG=",GOOGLE_API_KEY=${GOOGLE_API_KEY}"
  echo "==> Gemini API key: passed through"
else
  echo "==> Gemini API key: not set, service will use Vertex AI credentials"
fi

# ------------------------------------------------------------------ run
echo "==> Deploying to Cloud Run (Cloud Build compiles the image)"
$GCLOUD run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --project "$PROJECT" \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300 \
  --max-instances 3 \
  --set-env-vars "AMNESIA_USE_FIRESTORE=true,GOOGLE_CLOUD_PROJECT=${PROJECT},GOOGLE_CLOUD_LOCATION=${REGION},AMNESIA_MODEL=${AMNESIA_MODEL:-gemini-3.5-flash}${KEY_ARG}"

URL="$($GCLOUD run services describe "$SERVICE" --region "$REGION" --project "$PROJECT" --format='value(status.url)')"
echo
echo "==> Live at: $URL"

# ------------------------------------------------------------ scheduler
# The background pass is what makes this an agent rather than a web app: it
# runs whether or not anyone opens the page.
echo "==> Scheduling the hourly background pass"
if $GCLOUD scheduler jobs describe amnesia-distill --location "$REGION" --project "$PROJECT" >/dev/null 2>&1; then
  $GCLOUD scheduler jobs update http amnesia-distill \
    --location "$REGION" --project "$PROJECT" \
    --schedule "0 * * * *" --uri "${URL}/api/distill" --http-method POST
else
  $GCLOUD scheduler jobs create http amnesia-distill \
    --location "$REGION" --project "$PROJECT" \
    --schedule "0 * * * *" --uri "${URL}/api/distill" --http-method POST
fi

echo
echo "==> Done."
echo "    UI:        $URL"
echo "    Health:    $URL/healthz"
echo "    Card:      $URL/api/card.svg"
echo "    Distill:   curl -X POST $URL/api/distill"
