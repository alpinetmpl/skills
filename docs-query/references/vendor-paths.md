# Vendor paths — fast lookup for known vendors

Direct vendor + product → doc content path map. Use this to skip the root README + vendor README hop when you already recognize the product. **Authoritative source is always `<vendor>/README.md`** — this file is a curated cheat sheet that can drift.

All paths are relative to `~/github.com/alpinetmpl/docs/`.

> **Note:** the tables below reflect one real mirror's contents and are kept as a worked example. Curate this file to match what *your* docs repo actually holds — it earns its keep only when it agrees with disk.

## Table of contents

- [Submodule-backed docs (most common)](#submodule-backed-docs-most-common)
- [Web-mirrored docs](#web-mirrored-docs)
- [Tips](#tips)

## Submodule-backed docs (most common)

| Vendor | Product | Doc content path |
|--------|---------|------------------|
| Anthropic | Claude API docs | `claude-api-docs/` |
| Anthropic | Claude Code docs | `claude-code-docs/` |
| Anthropic | Cookbooks + Agent SDK | `anthropic/` |
| Argo Project | ArgoCD | `argoproj/argo-cd/docs` |
| Argo Project | Argo Helm Charts | `argoproj/argo-helm/charts/` |
| Argo Project | ArgoCD Vault Plugin | `argoproj-labs/argocd-vault-plugin/docs` |
| Cilium | Cilium | `cilium/cilium/Documentation` |
| ClickHouse | ClickHouse | `clickhouse/clickhouse-docs/docs` |
| CloudNativePG | CNPG Operator | `cloudnative-pg/docs/website/docs` |
| CloudNativePG | Barman Cloud Plugin | `cloudnative-pg/plugin-barman-cloud/web/docs` |
| CoreDNS | CoreDNS | `coredns/coredns/` |
| Crossplane | Crossplane | `crossplane/docs/content/v2.2` |
| Envoy Proxy | Envoy Gateway | `envoyproxy/gateway/site/content/en/v1.3/` |
| FastAPI | FastAPI | `fastapi/fastapi/docs` |
| Gethomepage | Homepage | `gethomepage/homepage/docs` |
| GitHub | GitHub docs (incl. Actions, Packages) | `github/docs/content` |
| Grafana | Grafana | `grafana/grafana/docs/sources` |
| Grafana | Loki | `grafana/loki/docs/sources` |
| Grafana | Mimir | `grafana/mimir/docs/sources/mimir` |
| Grafana | Tempo | `grafana/tempo/docs/sources/tempo` |
| Grafana | Alloy | `grafana/alloy/docs/sources` |
| Grafana | Beyla | `grafana/beyla/docs/sources` |
| Grafana | k6 | `grafana/k6-docs/docs/sources/k6/v1.7.x` |
| Grafana | k6 Studio | `grafana/k6-docs/docs/sources/k6-studio/` |
| Harbor | Harbor | `goharbor/website/docs` |
| HashiCorp | Vault | `hashicorp/web-unified-docs/content/vault/v1.21.x` |
| HashiCorp | Terraform | `hashicorp/web-unified-docs/content/terraform/v1.14.x` |
| K3s | K3s | `k3s-io/` |
| Karpenter | Karpenter | `karpenter/` |
| KEDA | KEDA | `kedacore/` |
| Keep | Keep | `keephq/keep/docs` |
| Kubernetes | Kubernetes | `kubernetes/website/content/en/docs` |
| Kyverno | Kyverno | `kyverno/website/src/content/docs/docs` |
| LangChain | LangGraph | `langchain-ai/docs/build/oss/python/langgraph/` |
| LangChain | DeepAgents | `langchain-ai/` |
| Langfuse | Langfuse | `langfuse/langfuse-docs/` |
| Linkerd | Linkerd | `linkerd/website/linkerd.io/content/2-edge` |
| MCP | Model Context Protocol | `modelcontextprotocol/` |
| OpenSearch | OpenSearch | `opensearch-project/` |
| Opstree | Redis Operator | `ot-container-kit/redis-operator/docs/content/en/docs/` |
| Oracle | Crossplane Provider OCI | `oracle/crossplane-provider-oci/docs/quickstart.md` |
| Plane | Plane | `makeplane/` |
| RabbitMQ | RabbitMQ Operator + site | `rabbitmq/` |
| Redpanda | Redpanda | `redpanda-data/` |
| Rook | Rook | `rook/` |
| Roundcube | Roundcube Webmail | `roundcube/roundcubemail/docs` |
| Slack | Slack CLI | `slackapi/` |
| Strimzi | Strimzi | `strimzi/` |
| Zitadel | Zitadel | `zitadel/zitadel/apps/docs/content` |

## Web-mirrored docs

| Vendor | Source | Path | Notes |
|--------|--------|------|-------|
| Anthropic | platform.claude.com | `anthropic/platform.claude.com/` | Claude Agent SDK docs |
| Cloudflare | developers.cloudflare.com | `cloudflare/developers.cloudflare.com/` | ~5,900 pages |
| Google Cloud | Vertex AI | `google/` | ~291 pages of Generative AI docs |
| Grafana | grafana.com | `grafana/grafana.com/` | Kubernetes Monitoring docs subset only |
| Kong | Kong AI Gateway | `kong/` | ~369 pages |
| LiteLLM (BerriAI) | docs.litellm.ai | `BerriAI/` | LiteLLM SDK + proxy mirror |
| Martin Baillie | martin.baillie.id | `martinbaillie/martin.baillie.id/` | Blog posts under `wrote/` |
| MiniMax | platform.minimax.io | `minimax/` | ~106 pages |
| Oracle | docs.oracle.com | `oracle/docs.oracle.com/en-us/iaas/Content/` | ~840 pages, has `TABLE_OF_CONTENTS.md` |
| Oracle | oracle.com | `oracle/oracle.com/` | OCI Compute pricing pages |
| Tailscale | tailscale.com | `tailscale/tailscale.com/` | Full site mirror, includes `/docs/` and Kubernetes Operator |

## Tips

- **Don't memorize this table — read it once when needed.** It's here so you skip the README hop, not so you commit it to context unprompted.
- **The full vendor list is in `~/github.com/alpinetmpl/docs/README.md`.** When in doubt about whether a vendor exists locally, that's the source of truth.
- **Doc-path conventions vary by upstream.** Some vendors put docs at `docs/`, others at `website/`, `site/content/`, `content/`, `src/content/docs/`. The vendor README always lists the exact path — don't guess.
- **Versioned paths drift.** When you see something like `hashicorp/web-unified-docs/content/vault/v1.21.x`, the `v1.21.x` segment moves with each upstream version bump. If the path in this file 404s, check the vendor README for the current version directory.
- **Submodules are read-only.** Never edit files under a submodule path — those changes are silently lost on the next refresh. Use the **docs-update** skill to update content properly.
