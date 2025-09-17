import asyncio
from gql import Client, gql
from gql.transport.websockets import WebsocketsTransport
from arrigo_api import login  # Importera login-funktionen från arrigo_api.py

async def subscribe_to_arrigo():
    # Konfiguration
    url = "wss://arrigo.svenskastenhus.se/arrigo/api/graphql/ws"  # Rätt URL för Arrigo-servern
    auth_token = f"Bearer {login()}"  # Hämta Auth Token automatiskt från arrigo_api.py

    # Skapa WebSocket-transport
    transport = WebsocketsTransport(
        url=url,
        headers={"Authorization": auth_token}
    )

    # Starta GraphQL-klienten utan att hämta schema
    async with Client(transport=transport, fetch_schema_from_transport=False) as session:
        # Prenumerera på uppdateringar
        subscription = gql("""
        subscription {
          data(path: "TGFuZHNrcm9uYS5zeXN0ZW1haXIuZmlsZQ==") {
            value
            path
            technicalAddress
            type
            timeStamp  # Ändrat från "timestamp" till "timeStamp"
          }
        }
        """)

        print("Lyssnar på uppdateringar från Arrigo...")
        async for result in session.subscribe(subscription):
            print("Uppdatering mottagen:", result)

# Kör klienten
if __name__ == "__main__":
    asyncio.run(subscribe_to_arrigo())