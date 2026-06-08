from pyromod import Client
import config
import db_manager

plugins = dict(root="plugins")

app = Client(
    "DongBot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    proxy=config.proxy,
    plugins=plugins,
)

if __name__ == "__main__":
    db_manager.init_db()
    print("===============================run====================================")
    app.run()