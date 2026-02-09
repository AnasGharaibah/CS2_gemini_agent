"""
Quartermaster Module for CS2 AI Coach
Responsible for Economy, Loadout, and Buy Phase logic.
"""

class Quartermaster:
    def __init__(self):
        # State tracking
        self.last_round_id = -1
        
        # MASTER LOCK: If True, we stop talking for the rest of the freeze time
        self.advice_given_this_round = False
        
        # Loss bonus constants (CS2 MR12 system)
        self.LOSS_BONUS_BASE = 1400
        self.LOSS_BONUS_INCREMENT = 500
        self.LOSS_BONUS_MAX = 3400

    def reset_round_state(self, current_round_id):
        """Resets flags if a new round has started."""
        if current_round_id != self.last_round_id:
            self.last_round_id = current_round_id
            self.advice_given_this_round = False 
            return True
        return False

    def get_team_data(self, map_data, player_team):
        if player_team == "CT":
            return map_data.get("team_ct", {})
        elif player_team == "T":
            return map_data.get("team_t", {})
        return {}

    def calculate_loss_bonus(self, consecutive_losses):
        if consecutive_losses is None:
            return self.LOSS_BONUS_BASE
        bonus = self.LOSS_BONUS_BASE + (consecutive_losses * self.LOSS_BONUS_INCREMENT)
        return min(bonus, self.LOSS_BONUS_MAX)

    def analyze(self, payload):
        """
        Main entry point. Analyzes the payload and returns ONE piece of advice.
        """
        # 1. Standard Checks
        if not payload or "map" not in payload or "player" not in payload:
            return []

        round_phase = payload["round"].get("phase")
        if round_phase != "freezetime":
            return []

        # 2. Check Master Lock
        if self.advice_given_this_round:
            return []

        # 3. Data Extraction
        current_round = payload["map"].get("round", -1) 
        self.reset_round_state(current_round)

        if self.advice_given_this_round:
            return []

        player = payload["player"]
        money = player.get("state", {}).get("money", 0)
        team_side = player.get("team") 
        weapons = player.get("weapons", {})
        
        team_data = self.get_team_data(payload["map"], team_side)
        loss_streak = team_data.get("consecutive_round_losses", 0)
        
        enemy_side = "T" if team_side == "CT" else "CT"
        enemy_data = self.get_team_data(payload["map"], enemy_side)
        enemy_streak = enemy_data.get("consecutive_round_wins", 0)

        advice_queue = []

        # We check conditions in order of importance. 
        # Once we find ONE valid piece of advice, we return it and lock the round.

        # Priority 1: Drop Requests (Being a good teammate is #1 if rich)
        if not advice_queue:
            drop_msg = self._check_drop_opportunity(money, weapons)
            if drop_msg:
                advice_queue.append(drop_msg)

        # Priority 2: Essentials (Forgot Kit/Armor?)
        if not advice_queue:
            kit_msg = self._check_essentials(player, money, team_side, payload["map"].get("name", ""), enemy_streak)
            if kit_msg:
                advice_queue.append(kit_msg)

        # Priority 3: Economy Strategy (General Buy/Save advice)
        if not advice_queue:
            strategy_msg = self._assess_economy_strategy(money, loss_streak, current_round, team_side)
            if strategy_msg:
                advice_queue.append(strategy_msg)

        # Priority 4: Utility (Optimization)
        if not advice_queue:
            util_msg = self._check_utility_needs(player, money)
            if util_msg:
                advice_queue.append(util_msg)

        if advice_queue:
            self.advice_given_this_round = True 
            return advice_queue

        return []



    def _assess_economy_strategy(self, money, loss_streak, round_num, team_side):
        if round_num == 0 or round_num == 12:
            if team_side == "T":
                return "Pistol round. Buy Armor or a Tec-9."
            else:
                return "Pistol round. Prioritize Armor or a Kit."

        next_income = self.calculate_loss_bonus(loss_streak)
        guaranteed_next_money = money + next_income
        RIFLE_FULL_BUY = 4100 
        
        if money < 2000 and guaranteed_next_money < RIFLE_FULL_BUY:
            return f"Hard Eco. We need ${RIFLE_FULL_BUY} for next round."

        if round_num in [1, 13] and loss_streak == 1 and 1500 < money < 3000:
             return "Force buy meta. Deagles or SMGs."

        if loss_streak >= 5 and money < RIFLE_FULL_BUY:
            return "Max loss bonus active. Force buy."

        if 4000 < money < 5200:
            return "You can buy a Rifle now, or save for an AWP."

        if 2800 <= money < 3800:
            return "Awkward money. Check teammate buys."

        return None

    def _check_essentials(self, player, money, team_side, map_name, enemy_score_streak):
        state = player.get("state", {})
        has_helmet = state.get("helmet", False)
        armor_val = state.get("armor", 0)
        has_kit = state.get("defusekit", False)
        
        is_defusal_map = "de_" in map_name 

        if team_side == "CT" and is_defusal_map and not has_kit:
            if money >= 400 and money > 3500:
                return "Buy a kit."
            elif money >= 400 and money < 2000:
                 return "Buy a kit, play passive."

        if armor_val < 35:
            if money >= 650:
                return "Buy Kevlar."

        elif not has_helmet and team_side == "CT":
            likely_enemy_has_ak = enemy_score_streak > 2
            money_is_tight = 3700 <= money <= 4100
            if likely_enemy_has_ak and money_is_tight:
                pass 
            elif money > 1000:
                return "Buy a helmet."
        
        elif not has_helmet and team_side == "T" and money > 1000:
            return "Buy a helmet."

        return None

    def _check_drop_opportunity(self, money, player_weapons):
        RICH_THRESHOLD = 8000
        MEGA_RICH_THRESHOLD = 11000
        
        if money < RICH_THRESHOLD:
            return None

        has_primary = False
        for k, w in player_weapons.items():
            if w.get("type") in ["Rifle", "SniperRifle", "Submachine Gun"]:
                has_primary = True
                break
        
        if money > MEGA_RICH_THRESHOLD:
            return "You have over 11k. Drop an AWP."
        
        if money > RICH_THRESHOLD and has_primary:
            return "You are rich. Drop rifles."
            
        return None

    def _check_utility_needs(self, player, money):
        MIN_BUY_BUFFER = 3900 
        if money < MIN_BUY_BUFFER:
            return None 

        weapons = player.get("weapons", {})
        team = player.get("team")
        
        has_smoke = False
        has_flash = False
        has_fire = False
        current_grenade_count = 0

        for key, w in weapons.items():
            if w.get("type") == "Grenade":
                current_grenade_count += 1
                name = w.get("name", "")
                if "smokegrenade" in name: has_smoke = True
                elif "flashbang" in name: has_flash = True
                elif "molotov" in name or "incgrenade" in name: has_fire = True

        fire_grenade_name = "Molotov" if team == "T" else "Incendiary"
        fire_grenade_cost = 400 if team == "T" else 600
        SMOKE_COST = 300
        FLASH_COST = 200

        if not has_smoke and money >= (MIN_BUY_BUFFER + SMOKE_COST):
            return "Buy a smoke."
        if not has_flash and money >= (MIN_BUY_BUFFER + FLASH_COST):
            return "Buy a flash."
        if not has_fire and money >= (MIN_BUY_BUFFER + fire_grenade_cost):
            return f"Buy an {fire_grenade_name}."
        if money > 6000 and current_grenade_count < 4:
            return "Fill utility slots."

        return None