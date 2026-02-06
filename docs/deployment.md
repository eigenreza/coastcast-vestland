# Deployment guide

The public release is available at the **[live CoastCast dashboard on Azure](https://coastcast-bergen.azurewebsites.net/)**.

This guide follows the same path used by the hosted application: verify one matched set of data and model artifacts, package it in a security-reviewed container, publish an immutable image, and promote that exact image to Azure. Keeping those steps explicit makes the release reproducible and keeps local, CI, and hosted behavior aligned.

## Local containers

Generate the approved model artifacts before building the public image:

```powershell
python -m coastcast.cli pipeline --config configs/base.yml
docker compose up --build
```

Services:

| Service | Port | Purpose |
| --- | ---: | --- |
| dashboard | 8501 | Interactive historical forecast explorer |
| api | 8000 | Versioned prediction API |
| pipeline | none | On-demand data and training job under the pipeline profile |

The image runs as the unprivileged `coastcast` user.

## Runtime release assets

The hosted dashboard is packaged with one reviewed, immutable runtime set:

- `data/gold/features.parquet`
- `artifacts/runtime/model_bundle.joblib`
- `artifacts/runtime/metrics.json`
- `artifacts/runtime/signature.json`
- `artifacts/runtime/test_predictions.parquet`

These files total less than 25 MB in the delivered build. They are explicitly included in source
control and the Docker build while raw responses, intermediate tables, local databases, experiment
stores, caches, and credentials remain excluded.

`constraints-runtime.txt` pins model-sensitive numerical and serialization libraries and a
security-reviewed Parquet runtime. The artifact signature records the model-sensitive versions so
an incompatible runtime cannot be mistaken for a model failure. MLflow remains an optional
training-time integration and is not installed in the public serving image.

## Azure App Service

The `infra/azure/main.bicep` template creates:

- a Linux Free (F1) App Service plan
- one externally accessible containerized web app
- HTTPS-only public access with HTTP/2
- managed-identity access to the existing Azure Container Registry
- the Streamlit runtime configuration on port 8501

The deployed interface is the same Streamlit application used locally. Azure provides the public HTTPS endpoint and managed container runtime; Streamlit provides the interactive forecasting experience. The current App Service plan is in West Central US, where the subscription has free Linux capacity, while the data and modeling scope remains Bergen.

Example deployment:

```powershell
az group create --name coastcast-rg --location norwayeast
az deployment group create `
  --resource-group coastcast-rg `
  --template-file infra/azure/main.bicep `
  --parameters location=westcentralus `
               appName=coastcast-bergen `
               servicePlanName=coastcast-bergen-f1 `
               containerImage=coastcastvestlandeigenreza.azurecr.io/coastcast-vestland:IMAGE_TAG `
               registryName=coastcastvestlandeigenreza `
               pullIdentityName=coastcast-vestland-pull
```

The existing pull identity must have the read-only `AcrPull` role on the registry. Registry passwords are not needed and should not be added to parameter files or repository secrets.

## Publishing sequence

1. Run the lint, test, and data-quality checks.
2. Run the complete 2017-2025 pipeline.
3. Review the generated metrics, interval coverage, and model-card statements.
4. Build the image with the approved artifact set.
5. Scan the finished image for known vulnerabilities.
6. Publish an immutable image tag to the selected registry.
7. Give the App Service web app read-only access to that image through its managed identity.
8. Deploy the exact reviewed tag.
9. Confirm the health endpoint and a known 2025 forecast in the rendered dashboard.

## CI/CD configuration

The quality workflow runs lint, tests, coverage, and a container build. The deployment workflow is manually triggered and uses Azure workload identity federation. Required repository or pipeline settings are:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`
- `AZURE_RESOURCE_GROUP`
- `AZURE_APP_NAME`
- `AZURE_APP_URL`
- `AZURE_ACR_NAME`

## Observability

Application logs are JSON and are available through App Service container logging when enabled. Recommended alerts include:

- failed health checks
- repeated 5xx responses
- startup failures caused by missing artifacts
- unexpected restart rate
- latency above the agreed service target

Model-quality monitoring is separate from service monitoring. It requires new verified observations and should compare every horizon with persistence.

## Rollback

Keep the previous immutable container tag. If health, schema, or model acceptance checks fail, set the App Service `linuxFxVersion` to the previous image and restart the web app. Because each image carries a matched feature table and model bundle, rollback does not require rebuilding data.
