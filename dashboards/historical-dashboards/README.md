## How to run the dashboards

### Installing Grafana Plugins

To use the dashboards in this deployment, you need to install the required Grafana plugins.

#### Required Plugins

- **yesoreyeram-infinity-datasource** - Enables querying multiple data sources and APIs
- **volkovlabs-echarts-panel** - Provides advanced charting capabilities

Add the following to your Kubernetes Deployment manifest under `spec.template.spec.containers[0].env`:

```yaml
- name: GF_INSTALL_PLUGINS
  value: yesoreyeram-infinity-datasource,volkovlabs-echarts-panel
```

This will automatically install the plugins when Grafana starts.

### Datasource Configuration

Inside Grafana, add two new datasources of **Infinity** type: 

1. **dt4mob-historic-infinity**
   - Base URL: `https://dt4mob.av.it.pt/historic`
   - Authentication: OAuth2
   - Fill in the required OAuth2 credentials

2. **dt4mob-infinity**
   - Base URL: `https://dt4mob.av.it.pt/api/2`
   - Authentication: OAuth2
   - Fill in the required OAuth2 credentials