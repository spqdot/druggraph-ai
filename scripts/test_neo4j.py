import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

uri = os.getenv("NEO4J_URI")
username = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")

print("Testing Neo4j connection...")
print(f"URI: {uri}")
print(f"Username: {username}")

driver = GraphDatabase.driver(
    uri,
    auth=(username, password)
)

try:
    driver.verify_connectivity()
    print("✅ Neo4j connection successful!")

    with driver.session() as session:
        result = session.run(
            "RETURN 'DrugGraph AI is connected!' AS message"
        )
        print(result.single()["message"])

finally:
    driver.close()