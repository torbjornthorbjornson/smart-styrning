import asyncio
from gql import Client, gql
from gql.transport.websockets import WebsocketsTransport

async def subscribe_to_arrigo():
    # Byt ut URL och Auth Token till dina egna värden
    transport = WebsocketsTransport(
        url="wss://myserver.com/arrigo/api/graphql/ws",  # Ändra till din Arrigo-server
        headers={"Authorization": "Bearer [your_auth_token]"}  # Ersätt med ditt Auth Token
    )

    async with Client(transport=transport, fetch_schema_from_transport=True) as session:
        # Prenumerera på uppdateringar
        subscription = gql("""
        subscription {
          data(path: "TGFuZHNrcm9uYS5zeXN0ZW1haXIuZmlsZQ==") {
            value
            path
            technicalAddress
            type
            timestamp
          }
        }
        """)

        print("Lyssnar på uppdateringar från Arrigo...")
        async for result in session.subscribe(subscription):
            print("Uppdatering mottagen:", result)

# Kör klienten
if __name__ == "__main__":
    asyncio.run(subscribe_to_arrigo())
