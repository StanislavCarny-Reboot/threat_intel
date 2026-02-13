import asyncio
from dotenv import load_dotenv
from workflows import get_intel, get_rss
import mlflow

mlflow.set_tracking_uri("http://localhost:5002")
mlflow.set_experiment("threat_intel_pipeline")
mlflow.autolog()


# Load environment variables
load_dotenv()


async def main():
    await get_rss.run()
    await get_intel.run()


if __name__ == "__main__":
    asyncio.run(main())
