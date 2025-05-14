from dynaconf import Dynaconf

SETTING_PATH = "/home/guozr/CODE/ObGrapper/cfg/writter.yaml"

settings = Dynaconf(
    envvar_prefix="DYNACONF",
    settings_files=[SETTING_PATH],
)

# `envvar_prefix` = export envvars with `export DYNACONF_FOO=bar`.
# `settings_files` = Load these files in the order.
