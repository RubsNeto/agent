from agents.models import Agent
from organizations.models import ApiKey

# Buscar a API Key
key = ApiKey.objects.get(key='sk_gIKDHVp_iYGw_wNS21g0gRH3B4-XlMv1bXH_fta1UBc')

print(f"API Key: {key.name}")
print(f"Padaria: {key.padaria.name} (slug: {key.padaria.slug})")
print(f"Agent vinculado à chave: {key.agent.slug if key.agent else 'Todos os agentes'}")
print(f"\nAgentes disponíveis nesta padaria:")

agentes = Agent.objects.filter(padaria=key.padaria)
for agente in agentes:
    print(f"  - Nome: {agente.name}")
    print(f"    Slug: {agente.slug}")
    print(f"    URL: /api/n8n/agents/{agente.slug}/config")
    print()
