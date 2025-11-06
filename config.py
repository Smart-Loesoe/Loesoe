import os
from pydantic import BaseModel
from dotenv import load_dotenv

# laad .env variabelen uit C:\Loesoe\loesoe\.env
load_dotenv()

class Settings(BaseModel):
    APP_ENV: str = os.getenv("APP_ENV", "dev")

settings = Settings()
