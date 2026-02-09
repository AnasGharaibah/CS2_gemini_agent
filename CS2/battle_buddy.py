import time

class BattleBuddy:
    def __init__(self):
        # --- Pro-Level Cooldowns ---
        # Prevents the coach from being annoying during a spray or rapid-fire trade
        self._last_reload_warn_time = 0
        self._last_blind_warn_time = 0
        self._last_damage_warn_time = 0
        self._last_health = 100
        self._last_helmet = True
        
        # Configuration: Seconds to wait before repeating the same warning
        self.COOLDOWN_RELOAD = 4.0      
        self.COOLDOWN_BLIND = 2.5       
        self.COOLDOWN_DMG = 3.0         

        # --- Weapon Knowledge Base ---
        # "Kill Threshold": Minimum bullets usually needed to secure a kill 
        # assuming decent aim but not aimbot.
        self.KILL_THRESHOLDS = {
            "Rifle": 5,           # AK/M4: You need ~4-5 bullets for a reliable burst/spray transfer
            "Submachine Gun": 8,  # MP9/Mac10: High fire rate + low dmg = needs more bullets
            "Pistol": 3,          # USP/Glock: Spamming happens, 1-2 isn't safe unless you tap
            "SniperRifle": 1,     # AWP/Scout: 1 is enough, but reload if safe
            "Shotgun": 1,         # Shells are individual
            "Machine Gun": 15     # Negev: You need pre-fire ammo
        }

    def analyze(self, current_data):
        """
        Orchestrates the analysis of the current game tick.
        Prioritizes survival warnings (Damage/Flash) over logistics (Ammo).
        """
        alerts = []
        current_time = time.time()
        
        # 1. Validation: Ensure player is alive and data exists
        player = current_data.get('player', {})
        if not player or player.get('activity') != 'playing':
            # Reset state on death/spectate so we don't warn immediately on respawn
            self._last_health = 100
            self._last_helmet = True
            return [] 

        state = player.get('state', {})
        weapons = player.get('weapons', {})

        # 2. PRIORITY 1: CRITICAL STATUS (Flash & Damage)
        # We check these first because they require instant reaction.
        
        # Flash Check
        flashed_val = state.get('flashed', 0)
        if flashed_val > 50 and (current_time - self._last_blind_warn_time > self.COOLDOWN_BLIND):
            alerts.append("Flashed! Get behind cover!")
            self._last_blind_warn_time = current_time

        # Damage Check
        current_hp = state.get('health', 100)
        current_armor = state.get('armor', 0)
        has_helmet = state.get('helmet', False)
        
        # Only analyze if health actually DROPPED (ignores spawn resets)
        if current_hp < self._last_health:
            damage_taken = self._last_health - current_hp
            if damage_taken > 0: # Sanity check
                # Check cooldown to prevent spamming during molotov/fire damage
                if current_time - self._last_damage_warn_time > self.COOLDOWN_DMG:
                    dmg_msg = self._analyze_damage(current_hp, damage_taken, current_armor, has_helmet)
                    if dmg_msg:
                        alerts.append(dmg_msg)
                        self._last_damage_warn_time = current_time

        # Update historical state for next tick
        self._last_health = current_hp
        self._last_helmet = has_helmet

        # 3. PRIORITY 2: LOGISTICS (Ammo)
        # Only check ammo if we aren't currently being destroyed by damage
        if not alerts: 
            if current_time - self._last_reload_warn_time > self.COOLDOWN_RELOAD:
                reload_msg = self._check_ammo(weapons)
                if reload_msg:
                    alerts.append(reload_msg)
                    self._last_reload_warn_time = current_time

        return alerts

    def _check_ammo(self, weapons):
        """
        Analyzes the active weapon for combat readiness.
        Distinguishes between 'Low Clip' (Reload needed) and 'Dry' (Switch weapon needed).
        """
        active_weapon = None
        
        # Find active weapon
        for key, w in weapons.items():
            if w.get('state') == 'active':
                active_weapon = w
                break
        
        if not active_weapon:
            return None

        w_type = active_weapon.get('type')
        clip = active_weapon.get('ammo_clip')
        reserve = active_weapon.get('ammo_reserve')

        # Ignore non-reloadable items (Knives, Grenades, C4, Taser)
        if clip is None or w_type in ["Knife", "Grenade", "C4", "Taser"]:
            return None

        # 1. CRITICAL: NO AMMO IN CLIP
        if clip == 0:
            if reserve > 0:
                return "Dry! Reload or swap!"
            else:
                return "Weapon empty! Drop it or switch!"

        # 2. TACTICAL: LOW AMMO (Based on Weapon Type)
        # Logic: Do I have enough bullets to kill 1 enemy if I miss a few shots?
        threshold = self.KILL_THRESHOLDS.get(w_type, 3) # Default safe fallback

        if clip <= threshold:
            # Special logic for AWP/Scout: You don't scream "Reload" on 1 bullet 
            # while scoping, but you warn if reserve is low.
            if w_type == "SniperRifle":
                if clip == 1 and reserve > 0:
                    return "One shot left, make it count."
                return None # Snipers are fine with low clips usually
            
            # For Rifles/SMGs/Pistols
            return f"Low ammo! Reload if safe."

        # 3. STRATEGIC: RESERVE AMMO CHECK
        # Warn if this is the absolute last magazine.
        if reserve < 10 and w_type in ["Rifle", "Submachine Gun"]:
            # Only warn if the clip is also getting low, otherwise it's distracting
            if clip < 10:
                return "Last mag! Conservation mode."

        return None

    def _analyze_damage(self, current_hp, damage_taken, current_armor, has_helmet):
        """
        Determines the impact of damage taken on playstyle.
        Considers 'Aim Punch' risks and specific HP thresholds.
        """
        # 1. ARMOR INTEGRITY CHECK
        # In CS2, if you have no armor, your screen shakes violently when hit (Aim Punch).
        if current_armor == 0 and current_hp > 0:
            return "No armor! Aim punch risk! Don't commit to sprays."
        
        # 2. HELMET CHECK
        # If you lost your helmet (or didn't buy one) and took headshot damage
        if self._last_helmet and not has_helmet:
            return "Helmet lost! One-tap risk."

        # 3. MASSIVE BURST DAMAGE (The "I almost died" check)
        # Taking >50 damage in one tick means you got headshot or AWP legged.
        if damage_taken >= 50:
            if current_hp <= 10:
                return "One HP! Play passive, don't peek."
            return f"Heavy hit (-{damage_taken})! Fall back and hold angle."

        # 4. THRESHOLD: "RED HP" (< 20 HP)
        # At this HP, a single grenade, molotov tick, or pistol body shot kills you.
        if current_hp <= 20:
            return f"Critical ({current_hp} HP)! You are one-shot to everything."

        # 5. THRESHOLD: "BODY SHOT RANGE" (< 40 HP)
        # At this HP, almost any rifle body shot will kill you instantly.
        # You cannot initiate duels anymore, you must trade.
        if current_hp <= 40:
             return "In body-shot range. If possible, play contact, let teammates peek first."