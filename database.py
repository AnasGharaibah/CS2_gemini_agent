from pymongo import MongoClient, ASCENDING
from datetime import datetime

client = MongoClient("mongodb://localhost:27017/")
db = client["CSGO"]

try:
    db.create_collection("matches")
    db.create_collection("rounds")
    db.create_collection("history")
except Exception:
    pass # Collections already exist


class CSGOStorage:
    def __init__(
        self,
        uri: str = "mongodb://localhost:27017/",
        db_name: str = "CSGO"
    ):
        self.client = MongoClient(uri)
        self.db = self.client[db_name]

        self.matches = self.db["matches"]
        self.rounds = self.db["rounds"]
        self.history = self.db["history"]

        self._create_indexes()

    # ---------------------------
    # INTERNAL
    # ---------------------------
    def _create_indexes(self):
        self.matches.create_index("matchId", unique=True)

        self.rounds.create_index(
            [("matchId", ASCENDING), ("roundNumber", ASCENDING)],
            unique=True
        )

        self.history.create_index(
            [
                ("matchId", ASCENDING),
                ("roundNumber", ASCENDING),
                ("timestamp", ASCENDING)
            ]
        )

    # ---------------------------
    # SAVE METHODS
    # ---------------------------
    def save_match(self, match_id: str, map_name: str):
        document = {
            "matchId": match_id,
            "mapName": map_name,
            "createdAt": datetime.utcnow()
        }

        self.matches.update_one(
            {"matchId": match_id},
            {"$setOnInsert": document},
            upsert=True
        )

    def save_round(self, match_id: str, round_number: int, round_data: dict, win : bool = False):
        document = {
            "matchId": match_id,
            "roundNumber": round_number,
            "win" : win,
            "data": round_data,
            "updatedAt": datetime.utcnow()
        }

        self.rounds.update_one(
            {"matchId": match_id, "roundNumber": round_number},
            {"$set": document},
            upsert=True
        )

    def save_history_snapshot(
        self,
        match_id: str,
        round_number: int,
        player_state: list
    ):
        document = {
            "matchId": match_id,
            "roundNumber": round_number,
            "timestamp": datetime.utcnow(),  # storage owns time
            "playerState": player_state
        }

        self.history.insert_one(document)

    # ---------------------------
    # GET METHODS
    # ---------------------------
    def get_matches(self):
        return list(self.matches.find({}, {"_id": 0}))

    def get_rounds(self, match_id: str):
        return list(
            self.rounds.find(
                {"matchId": match_id},
                {"_id": 0}
            ).sort("roundNumber", 1)
        )

    def get_round_history(self, match_id: str, round_number: int):
        return list(
            self.history.find(
                {"matchId": match_id, "roundNumber": round_number},
                {"_id": 0}
            ).sort("timestamp", 1)
        )

    def get_latest_state(self, match_id: str, round_number: int):
        return self.history.find_one(
            {"matchId": match_id, "roundNumber": round_number},
            sort=[("timestamp", -1)],
            projection={"_id": 0}
        )

    # ---------------------------
    # MAINTENANCE
    # ---------------------------
    def clear_database(self):
        self.matches.delete_many({})
        self.rounds.delete_many({})
        self.history.delete_many({})

    def close(self):
        self.client.close()



# Example usage:
def main():
    storage = CSGOStorage()

    storage.save_match("match_001", "de_mirage")

    storage.save_round(
        "match_001",
        1,
        {
            "winReason": "elimination",
            "winningTeam": "CT"
        }
    )

    storage.save_history_snapshot(
        "match_001",
        1,
        [
            {
                "playerId": "p1",
                "position": {"x": 100, "y": 200, "z": 0},
                "health": 84,
                "weapon": "m4a1_s"
            }
        ]
    )

    latest = storage.get_latest_state("match_001", 1)
    print(latest)

    storage.close()

if __name__ == "__main__":
    main()
