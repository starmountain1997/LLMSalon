import os.path as osp

from dynaconf import Dynaconf

PROJECT_ROOT = osp.dirname(osp.dirname(osp.abspath(__file__)))

SETTING_PATH = osp.join(PROJECT_ROOT, "src/settings.yaml")

settings = Dynaconf(
    envvar_prefix="DYNACONF",
    settings_files=[SETTING_PATH],
)

# `envvar_prefix` = export envvars with `export DYNACONF_FOO=bar`.
# `settings_files` = Load these files in the order.
