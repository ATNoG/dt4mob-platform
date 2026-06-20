# DT4MOB Alert Checker

CronJob service that checks latest load-cell values and keeps Grafana alert/alarm annotations in sync.

The Helm chart injects configuration through environment variables and mounts credentials from Kubernetes Secrets.

## How to run the CronJob
In dt4mob-platform:

1. Build container image:

```bash
docker build -t atnog-harbor.av.it.pt/dt4mob/alert-checker:latest services/dt4mob-alert-checker
```

2. Push the image to the registry:

```bash
docker push atnog-harbor.av.it.pt/dt4mob/alert-checker:latest
```

3. Run checks:

```bash
helm lint charts/dt4mob-alert-checker
helm template test charts/dt4mob-alert-checker
```

4. Create or update the Kubernetes Secret:

```bash
kubectl --kubeconfig ../cluster-staging/kubeconfig.yaml \
  create secret generic dt4mob-alert-checker-secret \
  --from-literal=username='YOUR_KEYCLOAK_USERNAME' \
  --from-literal=password='YOUR_KEYCLOAK_PASSWORD' \
  --from-literal=grafana-token='YOUR_GRAFANA_TOKEN' \
  -n digital4mob
```

5. Install or upgrade the chart directly:

```bash
helm upgrade --install dt4mob-alert-checker charts/dt4mob-alert-checker   -n digital4mob --kubeconfig ../cluster-staging/kubeconfig.yaml
```

6. Test with manual job:

**Delete old job before creating a new one**
```bash
kubectl --kubeconfig ../cluster-staging/kubeconfig.yaml \
  delete job dt4mob-alert-checker-manual -n digital4mob
```

**Create a manual job from the CronJob:**
```bash
kubectl --kubeconfig ../cluster-staging/kubeconfig.yaml \
  create job --from=cronjob/dt4mob-alert-checker-job \
  dt4mob-alert-checker-manual -n digital4mob
```

**Check the logs of the manual job:**
```bash
kubectl --kubeconfig ../cluster-staging/kubeconfig.yaml \
  logs -n digital4mob job/dt4mob-alert-checker-manual
```

**List jobs in the namespace:**
```bash
kubectl --kubeconfig ../cluster-staging/kubeconfig.yaml \
  get jobs -n digital4mob
```

