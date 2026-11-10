# instagram

Herramienta de línea de comandos que automatiza un navegador con Playwright para obtener las listas de seguidores y seguidos de una cuenta de Instagram y compararlas.

## Características

- Inicio de sesión manual y reutilización de la sesión guardada (`data/session.json`)
- Obtención de las listas de seguidores y seguidos
- Comparación de ambas listas para guardar quién no devuelve el seguimiento (`--compare`)
- Pruebas unitarias con mocks y pruebas de integración con navegador real

## Stack

| Capa | Tecnología |
|---|---|
| Lenguaje | Python 3.12 |
| Automatización | Playwright |
| Configuración | python-dotenv |
| Pruebas y calidad | pytest, ruff, GitHub Actions (`.github/workflows/ci.yaml`) |

## Uso

```bash
git clone https://github.com/netfoor/instagram.git
cd instagram
uv sync
uv run playwright install chromium
uv run main.py --login
uv run main.py --compare
```

## Aviso

La automatización de Instagram puede ir contra sus términos de uso. El repositorio se conserva solo como referencia técnica.

## Estado

Archivado. Proyecto personal (agosto de 2026), sin mantenimiento.
