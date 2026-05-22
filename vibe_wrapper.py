import os, sys

wrapper_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(wrapper_dir, 'vibe-trading.env')
if os.path.exists(env_path):
    with open(env_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            eq = line.find('=')
            if eq > 0:
                k = line[:eq].strip()
                v = line[eq+1:].strip()
                os.environ[k] = v

proxy_url = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy') or os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
if not proxy_url:
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Internet Settings')
        proxy_server, _ = winreg.QueryValueEx(key, 'ProxyServer')
        winreg.CloseKey(key)
        if proxy_server and proxy_server.strip():
            proxy_addr = proxy_server.strip()
            if not proxy_addr.startswith('http'):
                proxy_addr = 'http://' + proxy_addr
            os.environ.setdefault('HTTPS_PROXY', proxy_addr)
            os.environ.setdefault('HTTP_PROXY', proxy_addr)
    except Exception:
        pass

os.environ['VIBE_TRADING_HOME'] = os.path.join(wrapper_dir, 'vibe-data')
os.environ['VIBE_TRADING_ALLOWED_RUN_ROOTS'] = os.path.join(wrapper_dir, 'vibe-data', 'runs')

site_pkg = r'D:\vibe-trading-venv\Lib\site-packages'
if site_pkg not in sys.path:
    sys.path.insert(0, site_pkg)

from pathlib import Path
import cli
import src.agent.loop as loop_mod
import src.agent.context as context_mod
import src.session.store as store_mod
import src.session.search as search_mod
import src.swarm.models as swarm_models
import src.swarm.presets as swarm_presets

FALLBACK_MODEL = os.environ.get('LANGCHAIN_FALLBACK_MODEL_NAME', 'gemini-3-flash')

SWARM_MAX_ITERATIONS = int(os.environ.get('VIBE_SWARM_MAX_ITERATIONS', '20'))
SWARM_TIMEOUT_SECONDS = int(os.environ.get('VIBE_SWARM_TIMEOUT_SECONDS', '300'))
SWARM_WRAP_UP_RATIO = float(os.environ.get('VIBE_SWARM_WRAP_UP_RATIO', '0.65'))
MAIN_LOOP_MAX_ITERATIONS = int(os.environ.get('VIBE_MAIN_LOOP_MAX_ITERATIONS', '25'))

_orig_build_system_prompt = context_mod.ContextBuilder.build_system_prompt

def _patched_build_system_prompt(self, user_message=""):
    result = _orig_build_system_prompt(self, user_message)
    suffix = "\n\n## Language\n- Always respond in Simplified Chinese (简体中文). Never use English unless explicitly requested."
    _LOCAL_DATA_KEYWORDS = ['信号', '清仓', '仓位', '满仓', '底仓', '观望', '中证500', 'zz500', 'MA20', '量化']
    if any(kw in user_message for kw in _LOCAL_DATA_KEYWORDS):
        try:
            csv_path = os.path.join(wrapper_dir, 'zz500_factors.csv')
            if os.path.exists(csv_path):
                with open(csv_path, encoding='utf-8') as f:
                    lines = f.readlines()
                header = lines[0] if lines else ''
                tail = lines[-10:] if len(lines) > 10 else lines[1:]
                snippet = header + ''.join(tail)
                suffix += "\n\n## 本地量化信号数据（最近数日）\n" + snippet
        except Exception:
            pass
    return result + suffix

context_mod.ContextBuilder.build_system_prompt = _patched_build_system_prompt

_orig_create_run = swarm_presets.create_run

def _patched_create_run(preset_name, user_vars=None):
    run = _orig_create_run(preset_name, user_vars=user_vars)
    for i, agent in enumerate(run.agents):
        if agent.max_iterations > SWARM_MAX_ITERATIONS:
            run.agents[i] = agent.model_copy(update={'max_iterations': SWARM_MAX_ITERATIONS})
        if agent.timeout_seconds > SWARM_TIMEOUT_SECONDS:
            run.agents[i] = run.agents[i].model_copy(update={'timeout_seconds': SWARM_TIMEOUT_SECONDS})
    return run

swarm_presets.create_run = _patched_create_run

_orig_loop_init = loop_mod.AgentLoop.__init__

def _patched_loop_init(self, registry, llm, memory=None, event_callback=None, max_iterations=MAIN_LOOP_MAX_ITERATIONS, persistent_memory=None):
    _orig_loop_init(self, registry, llm, memory=memory, event_callback=event_callback, max_iterations=max_iterations, persistent_memory=persistent_memory)

loop_mod.AgentLoop.__init__ = _patched_loop_init

try:
    import src.swarm.worker as swarm_worker
    swarm_worker._WRAP_UP_RATIO = SWARM_WRAP_UP_RATIO
    swarm_worker._DEFAULT_MAX_ITERATIONS = SWARM_MAX_ITERATIONS
    swarm_worker._DEFAULT_TIMEOUT_SECONDS = SWARM_TIMEOUT_SECONDS
except Exception:
    pass

try:
    import src.providers.llm as llm_mod
    _orig_build_llm = llm_mod.build_llm

    def _patched_build_llm(*, model_name=None, callbacks=None):
        primary = _orig_build_llm(model_name=model_name, callbacks=callbacks)
        try:
            fallback = _orig_build_llm(model_name=FALLBACK_MODEL, callbacks=callbacks)
            return primary.with_fallbacks([fallback])
        except Exception:
            return primary

    llm_mod.build_llm = _patched_build_llm
except Exception:
    pass

new_home = Path(os.environ['VIBE_TRADING_HOME'])
new_home.mkdir(parents=True, exist_ok=True)

for mod in [cli]:
    mod.AGENT_DIR = new_home
    mod.RUNS_DIR = new_home / "runs"
    mod.SWARM_DIR = new_home / ".swarm" / "runs"
    mod.SESSIONS_DIR = new_home / "sessions"
    mod.UPLOADS_DIR = new_home / "uploads"

loop_mod.RUNS_DIR = new_home / "runs"

for d in [cli.RUNS_DIR, cli.SESSIONS_DIR, cli.UPLOADS_DIR, cli.SWARM_DIR, loop_mod.RUNS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

if hasattr(store_mod, 'SESSIONS_DIR'):
    store_mod.SESSIONS_DIR = new_home / "sessions"
if hasattr(search_mod, 'SESSIONS_DIR'):
    search_mod.SESSIONS_DIR = new_home / "sessions"

cli.main()
