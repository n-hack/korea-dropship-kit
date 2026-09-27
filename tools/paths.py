"""置き場を1か所で決める … 既定はこのフォルダの1つ上（KIT_HOME で変えられる）
  config/ … 鍵と設定（リポジトリには入れない）
  data/   … 台帳・記録（リポジトリには入れない）"""
import os

BASE = os.environ.get("KIT_HOME", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONF = os.path.join(BASE, "config")
DATA = os.path.join(BASE, "data")


def conf(name):
    return os.path.join(CONF, name)


def data(name):
    os.makedirs(DATA, exist_ok=True)
    return os.path.join(DATA, name)
