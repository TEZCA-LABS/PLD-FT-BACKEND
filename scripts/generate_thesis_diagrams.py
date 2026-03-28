"""
Generate Chapter 3 thesis diagrams and copy final PNG assets to SEMINARIO2/Imagenes.

Outputs (exact names expected by Capitulo3.tex):
- fig3_01_arquitectura_global.png
- fig3_04_deployment_docker.png
- fig3_06_seq_search_hibrida.png
- fig3_07_seq_ai_chat.png

Requirements:
- Python packages: diagrams, graphviz
- System Graphviz installed
- Mermaid CLI available as `mmdc` for sequence diagrams
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from diagrams import Cluster, Diagram, Edge
from diagrams.onprem.client import Users
from diagrams.onprem.compute import Server
from diagrams.onprem.container import Docker
from diagrams.onprem.database import PostgreSQL
from diagrams.onprem.inmemory import Redis
from diagrams.onprem.network import Nginx
from diagrams.onprem.queue import Celery
from diagrams.programming.framework import Fastapi
from diagrams.programming.language import Python


def _link(src, dst, label: str | None = None, color: str | None = None, style: str | None = None) -> None:
    edge_kwargs = {}
    if label is not None:
        edge_kwargs["label"] = label
    if color is not None:
        edge_kwargs["color"] = color
    if style is not None:
        edge_kwargs["style"] = style
    edge = Edge(**edge_kwargs)
    src.connect(dst, edge)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _seminario_images_dir() -> Path:
    root = _repo_root().parent
    return root / "SEMINARIO2" / "Imagenes"


def _tmp_output_dir() -> Path:
    out_dir = _repo_root() / "docs" / "diagrams" / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _copy_png(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(f"Expected PNG not found: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def generate_fig3_01_architecture(out_dir: Path) -> Path:
    filename = out_dir / "fig3_01_arquitectura_global"
    graph_attr = {
        "fontsize": "20",
        "bgcolor": "white",
        "pad": "0.3",
    }

    with Diagram(
        "Arquitectura Global PLD-FT",
        show=False,
        filename=str(filename),
        direction="LR",
        graph_attr=graph_attr,
    ):
        user = Users("Usuario/Analista")

        with Cluster("Capa de Presentacion"):
            frontend = Nginx("Frontend React + Vite")

        with Cluster("Capa de Servicios"):
            api = Fastapi("Backend FastAPI")
            worker = Celery("Celery Worker")

        with Cluster("Capa de Persistencia"):
            db = PostgreSQL("PostgreSQL + pgvector")
            broker = Redis("Redis Broker")

        with Cluster("Servicios Externos"):
            llm = Python("OpenAI LLM")
            with Cluster("Fuentes de Sanciones"):
                un = Server("UN")
                sat = Server("SAT")
                mex = Server("MEX")

        _link(user, frontend)
        _link(frontend, api)
        _link(api, db, label="SQL + vector")
        _link(api, broker, label="enqueue")
        _link(broker, worker, label="dequeue")
        _link(worker, db, label="sync + embeddings")

        _link(api, llm, label="RAG", color="orange", style="dashed")
        _link(worker, llm, label="embeddings", color="orange", style="dashed")

        _link(un, worker, label="sync")
        _link(sat, worker, label="sync")
        _link(mex, worker, label="sync")

    return filename.with_suffix(".png")


def generate_fig3_04_deployment(out_dir: Path) -> Path:
    filename = out_dir / "fig3_04_deployment_docker"
    graph_attr = {
        "fontsize": "20",
        "bgcolor": "white",
        "pad": "0.3",
    }

    with Diagram(
        "Deployment Docker Backend",
        show=False,
        filename=str(filename),
        direction="LR",
        graph_attr=graph_attr,
    ):
        user = Users("Usuario")

        with Cluster("Host Docker"):
            docker_net = Docker("docker network")

            with Cluster("App Services"):
                backend = Fastapi("backend")
                worker = Celery("worker")

            with Cluster("Data Services"):
                db = PostgreSQL("db (volume)")
                redis = Redis("redis")

            _link(docker_net, backend)
            _link(docker_net, worker)
            _link(docker_net, db)
            _link(docker_net, redis)

        _link(user, backend)
        _link(backend, db, label="depends_on + healthcheck")
        _link(backend, redis, label="broker")
        _link(worker, redis, label="queue")
        _link(worker, db, label="writes")

    return filename.with_suffix(".png")


def generate_fig3_02_erd(out_dir: Path) -> Path:
    filename = out_dir / "fig3_02_erd_simplificado"
    graph_attr = {
        "fontsize": "20",
        "bgcolor": "white",
        "pad": "0.3",
    }

    with Diagram(
        "ERD Simplificado Operativo",
        show=False,
        filename=str(filename),
        direction="LR",
        graph_attr=graph_attr,
    ):
        with Cluster("Identidad y Acceso"):
            user = Server("user\nPK id\nusername\nrole")
            role_permission = Server("role_permission\nPK id\nmodule\nallowed_roles")

        with Cluster("Sanciones y Entidades"):
            entity_profile = Server("entity_profile\nPK id\nprimary_name")
            sanction = Server("sanction\nPK id\nFK profile_id\nentity_name\nsource")

        with Cluster("Auditoria"):
            audit_log = Server("audit_log\nPK id\nFK user_id\naction\ntimestamp")

        with Cluster("Inteligencia Asistida"):
            ai_session = Server("ai_chat_session\nPK id\nFK user_id\nstatus\ncreated_at")
            ai_message = Server("ai_chat_message\nPK id\nFK session_id\nrole\ncreated_at")
            ai_attachment = Server("ai_chat_attachment\nPK id\nFK session_id\nfile_name\nstatus")

        _link(user, ai_session, label="1:N")
        _link(ai_session, ai_message, label="1:N")
        _link(ai_session, ai_attachment, label="1:N")
        _link(user, audit_log, label="1:N")
        _link(entity_profile, sanction, label="1:N")
        _link(role_permission, user, label="matriz por rol")

    return filename.with_suffix(".png")


def generate_fig3_03_backend_layers(out_dir: Path) -> Path:
    filename = out_dir / "fig3_03_backend_capas"
    graph_attr = {
        "fontsize": "20",
        "bgcolor": "white",
        "pad": "0.3",
    }

    with Diagram(
        "Arquitectura Backend por Capas",
        show=False,
        filename=str(filename),
        direction="TB",
        graph_attr=graph_attr,
    ):
        with Cluster("API Layer"):
            api_router = Fastapi("FastAPI Routers\nauth/users/search/intelligence/audit/roles")

        with Cluster("Service Layer"):
            search_svc = Server("Search Service\nexact + fuzzy + vector")
            intelligence_svc = Server("Intelligence Service\nsesiones + mensajes + export")
            audit_svc = Server("Audit Service\nregistro de eventos")

        with Cluster("Persistence Layer"):
            db = PostgreSQL("PostgreSQL + pgvector")

        with Cluster("Async Processing"):
            worker = Celery("Celery Worker\nETL sync tasks")
            broker = Redis("Redis Broker")

        with Cluster("RAG / Integraciones Externas"):
            rag = Server("RAG Retrieval")
            llm = Python("OpenAI LLM")

        security = Server("Seguridad JWT/RBAC")
        observability = Server("Auditoria transversal")

        _link(api_router, search_svc)
        _link(api_router, intelligence_svc)
        _link(api_router, audit_svc)
        _link(api_router, security, label="dependency")

        _link(search_svc, db)
        _link(intelligence_svc, db)
        _link(audit_svc, db)

        _link(api_router, broker, label="enqueue")
        _link(broker, worker, label="dequeue")
        _link(worker, db, label="sync")

        _link(intelligence_svc, rag, label="retrieve")
        _link(rag, db, label="contexto")
        _link(rag, llm, label="generate", style="dashed", color="orange")

        _link(search_svc, observability)
        _link(intelligence_svc, observability)
        _link(observability, db)

    return filename.with_suffix(".png")


def _render_mermaid(in_file: Path, out_png: Path) -> None:
    mmdc = shutil.which("mmdc")
    if not mmdc:
        raise RuntimeError(
            "Mermaid CLI 'mmdc' not found. Install with: npm i -g @mermaid-js/mermaid-cli"
        )

    cmd = [
        mmdc,
        "-i",
        str(in_file),
        "-o",
        str(out_png),
        "-b",
        "white",
        "-w",
        "2200",
    ]
    subprocess.run(cmd, check=True)


def generate_sequence_pngs(out_dir: Path) -> tuple[Path, Path]:
    diagrams_dir = _repo_root() / "docs" / "diagrams"
    src_search = diagrams_dir / "fig3_06_seq_search_hibrida.mmd"
    src_chat = diagrams_dir / "fig3_07_seq_ai_chat.mmd"

    out_search = out_dir / "fig3_06_seq_search_hibrida.png"
    out_chat = out_dir / "fig3_07_seq_ai_chat.png"

    _render_mermaid(src_search, out_search)
    _render_mermaid(src_chat, out_chat)

    return out_search, out_chat


def generate_frontend_modular_png(out_dir: Path) -> Path:
    diagrams_dir = _repo_root() / "docs" / "diagrams"
    src_frontend = diagrams_dir / "fig3_05_frontend_modular.mmd"
    out_frontend = out_dir / "fig3_05_frontend_modular.png"
    _render_mermaid(src_frontend, out_frontend)
    return out_frontend


def main() -> None:
    out_dir = _tmp_output_dir()
    final_dir = _seminario_images_dir()

    print(f"[1/7] Generating fig3_01 in {out_dir}")
    fig1 = generate_fig3_01_architecture(out_dir)

    print(f"[2/7] Generating fig3_04 in {out_dir}")
    fig4 = generate_fig3_04_deployment(out_dir)

    print(f"[3/7] Rendering Mermaid sequences in {out_dir}")
    fig6, fig7 = generate_sequence_pngs(out_dir)

    print(f"[4/7] Generating fig3_02 ERD in {out_dir}")
    fig2 = generate_fig3_02_erd(out_dir)

    print(f"[5/7] Generating fig3_03 backend layers in {out_dir}")
    fig3 = generate_fig3_03_backend_layers(out_dir)

    print(f"[6/7] Rendering fig3_05 frontend modular in {out_dir}")
    fig5 = generate_frontend_modular_png(out_dir)

    print(f"[7/7] Copying final assets to {final_dir}")
    _copy_png(fig1, final_dir / "fig3_01_arquitectura_global.png")
    _copy_png(fig2, final_dir / "fig3_02_erd_simplificado.png")
    _copy_png(fig3, final_dir / "fig3_03_backend_capas.png")
    _copy_png(fig4, final_dir / "fig3_04_deployment_docker.png")
    _copy_png(fig5, final_dir / "fig3_05_frontend_modular.png")
    _copy_png(fig6, final_dir / "fig3_06_seq_search_hibrida.png")
    _copy_png(fig7, final_dir / "fig3_07_seq_ai_chat.png")

    print("Done. Generated assets:")
    print("- fig3_01_arquitectura_global.png")
    print("- fig3_02_erd_simplificado.png")
    print("- fig3_03_backend_capas.png")
    print("- fig3_04_deployment_docker.png")
    print("- fig3_05_frontend_modular.png")
    print("- fig3_06_seq_search_hibrida.png")
    print("- fig3_07_seq_ai_chat.png")


if __name__ == "__main__":
    main()
