// Package loki implements Theorycraft's own ("project Loki") backend endpoints
// that sit in front of AccelByte: the client-config service and the account/auth
// service the Steam login actually talks to.
//
// Observed from the client (Loki.log):
//   - GET https://client-config-jx-prod.../configuration/public?language=en
//     (LogClientConfig; non-fatal — client reaches the menu even on failure)
//   - Steam login -> POST https://accounts.projectloki.theorycraftgames.com/...
//     (LogLokiAuthManager "Attempting to login with Steam"; on failure:
//     "Auth Failure 14005 Request not sent")
//
// The exact accounts path/schema is still being captured; until known, those
// routes fall through to the capture stub. This package owns what we've confirmed.
package loki

import (
	"bytes"
	"encoding/json"
	"image"
	"image/color"
	"image/draw"
	"image/png"
	"net/http"
	"os"
	"sort"
	"strconv"
	"strings"
	"time"
)

type Service struct{}

// envOr returns the environment variable v, or def when it is unset or empty.
// Used for the operator-overridable knobs on the client-config payload.
func envOr(v, def string) string {
	if s := os.Getenv(v); s != "" {
		return s
	}
	return def
}

func New() *Service { return &Service{} }

func (s *Service) Register(mux *http.ServeMux) {
	// Master client-config: service registry + display-name limits.
	// Two surfaces return the same ClientConfiguration: /configuration/public (fetched
	// once, pre-auth) and /configuration/client (polled ~1/s by ClientConfigManager,
	// post-auth). The {} catch-all left /configuration/client empty, so ClientVersions
	// was empty and Comp_MainMenu_QueueController.IsClientVersionValid returned false —
	// which fails CanControlQueue and blocks activity selection with
	// "Unable to modify activity". Serving the same config (with ClientVersions) here
	// lets the version check pass.
	mux.HandleFunc("GET /configuration/public", s.handleClientConfig)
	mux.HandleFunc("GET /configuration/client", s.handleClientConfig)

	// FK-17 banner probe assets (see handleClientConfig's bannerConfigs block).
	// The banner record carries SplashImageURL/IconUrl (remote images the client
	// fetches itself) and ActionURL (opened when ActionType == WebURL). Serving all
	// three locally makes the probe self-contained AND gives three independent
	// receipts in docs/capture.log: a splash fetch, an icon fetch, and — only if the
	// banner is actually clicked — a news.html fetch.
	mux.HandleFunc("GET /revival/banner/splash.png", s.handleBannerSplash)
	mux.HandleFunc("GET /revival/banner/icon.png", s.handleBannerIcon)
	mux.HandleFunc("GET /revival/banner/news.html", s.handleBannerPage)

	// PostAuth service (resolved from ServiceHostnames["postauth"]). The game
	// calls {base}/postauth/... — e.g. reconcileRoles after login.
	mux.HandleFunc("POST /postauth/reconcileRoles", s.handleReconcileRoles)
	mux.HandleFunc("POST /reconcileRoles", s.handleReconcileRoles)
}

// handleReconcileRoles answers the post-login role reconcile (PostAuthReconcileResponse).
// The AuthManager reads DisplayNameTagValidation from here, which drives the
// "CHOOSE DISPLAY NAME AND TAG" screen limits (otherwise shown as 0 and 0).
func (s *Service) handleReconcileRoles(w http.ResponseWriter, r *http.Request) {
	// PostAuthReconcileResponse fields confirmed from the binary: Unique_display_name
	// and Other_display_name. A non-empty unique_display_name tells the AuthManager
	// the account is already named, so ELokiAuthState goes Authorized instead of
	// AwaitingUniqueDisplayName -> the onboarding screen is skipped.
	writeJSON(w, map[string]any{
		"roles":               []any{},
		"steamId":             r.URL.Query().Get("steam"),
		"mfa_required":        false,
		"unique_display_name": "Reviver#0001",
		"other_display_name":  "Reviver",
		// casing hedges
		"Unique_display_name": "Reviver#0001",
		"Other_display_name":  "Reviver",
		"uniqueDisplayName":   "Reviver#0001",
	})
}

// handleClientConfig returns the ClientConfiguration the game relies on: a
// service registry (looked up by name, e.g. "postauth" — which handles the
// display-name/tag step) plus DisplayNameTagValidation limits for the
// "CHOOSE DISPLAY NAME AND TAG" screen. Field names confirmed from the binary;
// UE JSON matching is case-insensitive.
func (s *Service) handleClientConfig(w http.ResponseWriter, r *http.Request) {
	const base = "http://localhost:8080"
	// ServiceHostnames is a TMap<serviceName, url> (confirmed: ServiceHostnames_Key).
	// GetServiceAddress(name) looks up by service name; the game then calls
	// {url}/{name}/{endpoint}.
	services := []string{
		"postauth", "clientconfig", "iam", "platform", "basic", "lobby",
		"session", "matchmaking", "social", "cloudsave", "telemetry", "gateway",
		"mmr", "party", "storefront", "progression", "mailbox", "referral",
		"personalization", "inventory", "playerstats", "matchhistory",
		// Added after the client logged "Could not find service address for
		// service <name>" for these exact keys. Without an address the client
		// builds a host-less URL ("No host part in the URL" / "Invalid response
		// received") — e.g. /content-service/manifest and /discord-api/account/token.
		// Note: the service NAME (lookup key) has no hyphen; the URL PATH segment
		// the client appends does (content-service, discord-api, core-game).
		"contentservice", "discordapi", "coregame",
	}
	// ServiceHostnames is TMap<serviceName, FString url> (confirmed: the client
	// logged "Object used as String" when we sent structs). Plain string values.
	hostnames := map[string]any{}
	for _, name := range services {
		hostnames[name] = base
	}
	// messaging is a websocket service: when its address is absent the client
	// logs "Messenger connection failed Bad protocol ''. Use either 'ws', 'wss',
	// or 'wss+insecure'", i.e. it uses the value directly as the ws URL. Give it a
	// ws:// scheme so the protocol parses. (The ws handshake itself is still TODO —
	// our server doesn't speak websocket yet, so it will then fail at upgrade like
	// the lobby service does.)
	hostnames["messaging"] = "ws://localhost:8080"
	// Include eTag + lastUpdated: the client likely only *applies* a fetched
	// config that is newer than its current (default 0), so without these the
	// parsed config is dropped and ServiceHostnames stays empty.
	// ClientVersions is the supported-version list; if the client's build isn't
	// in it the game shows "UPDATE REQUIRED". Build is release2.4.live-156430.
	// S73 probe: serve featureToggles. ClientConfiguration.FeatureToggles is TMap<FString, FFeatureToggle>
	// where FFeatureToggle{ Config: TMap<FString,FString> } (RE'd live). The DS client spams
	// "ULokiGameFeatureToggles::Get <X> called when feature toggles were not ready" and stays on the tutorial
	// LOADING screen. TEST: does populating the GLOBAL config toggle set flip readiness (config-gated), or is
	// readiness set only at server round-start (round-gated)? Serve the observed gameplay toggles enabled.
	// (Malformed = whole config dropped silently per the validity model, so this is safe to iterate.)
	//
	// ★ S85 (2026-07-21) ANSWERED: NOT config-payload-gated. Readiness is PER-PlayerController — the delegates
	// OnClientGameFeatureTogglesReady / OnAnyClientGameFeatureToggleChanged / ...ReadyOrChanged live on
	// LokiPlayerController (schema.txt:26932). Ruled out by measurement (docs/session-85 §"feature toggles"):
	// the toggles are NOT delivered by any PC replicated prop (only LokiPlayerCheats+bIsAdmin), any PC Client
	// RPC (none toggle-related), any GameState replicated prop (none of the 43 is config/toggle/auth), or any
	// separate HTTP endpoint (client hits ONLY /configuration/{public,client} + /mailbox/config/version — this
	// featureToggles payload IS received, since ServiceHostnames from the same doc works). Errors appear 0x at
	// the menu and only ~2s AFTER DS travel => readiness is set by the per-match game-feature resolution the
	// real server drives during round-start (round-gated), which the stub doesn't run. Static string-xref RE of
	// ULokiGameFeatureToggles::Get is packer-blocked (format string uncommitted, same S61 login wall). Next to
	// crack it = dumpimage the now-committed .text + offline disasm, OR a client-side ready-bool shim (force).
	// ⚠⚠⚠ THE SUB-KEY IS "enabled", NOT "default" — and getting that wrong made this ENTIRE
	// payload inert from S73 until S120 (2026-08-15).
	//
	// MEASURED from the shipped asset. The game gates UI on a reusable declarative widget,
	// WBP_UI_ClientConfigVisbilityToggleWidget_C (the typo is the game's), whose ubergraph does:
	//
	//     cfg   = GetClientConfigManager()->GetClientConfiguration()
	//     entry = Map_Find(cfg.FeatureToggles, FeatureKey)   // FeatureKey  = asset property
	//         if not found -> use IsEnabledByDefault
	//     value = Map_Find(entry.Config,       ConfigKey)    // ConfigKey   = asset property,
	//         if not found -> use IsEnabledByDefault         //   CDO default = "enabled"
	//     enabled = ToBool(value)
	//
	// We were writing Config["default"], so Map_Find(Config, "enabled") MISSED on every key we
	// have ever sent, and every gate silently fell back to its own IsEnabledByDefault.
	//
	// ★ THE STOREFRONT PROVED IT, three-for-three, before the fix — a natural positive control:
	//     PacksConfigToggle_1   FeatureKey "supporterpacks"  IsEnabledByDefault true   -> VISIBLE
	//     RedeemConfigToggle_1  FeatureKey "redeemcode"      IsEnabledByDefault true   -> VISIBLE
	//     StorageConfigToggle_1 FeatureKey "exchangetokens"  (no default => false)     -> HIDDEN
	// i.e. the two visible tabs were visible *despite* us, and the one that needed us was dark.
	//
	// Both sub-keys are sent now. FFeatureToggle.Config is TMap<FString,FString>, so an extra
	// entry is inert — "default" is kept in case any other consumer reads that spelling, and this
	// costs nothing to hold. ⚠ Do NOT drop "enabled" to "tidy up".
	ftVal := func(on string) map[string]any {
		return map[string]any{"config": map[string]string{"enabled": on, "default": on}}
	}
	ftEnabled := ftVal("true")
	// Keys added at runtime via AGS_UI_TOGGLES_EXTRA. Tracked so the eTag can reflect them —
	// see the eTag comment below; a changed payload under an unchanged eTag is a silent no-op.
	var extras []string
	featureToggles := map[string]any{
		"CursorCharacterAim":        ftEnabled,
		"AttachAudioListenerToHero": ftEnabled,
		"DeadSpectatorCameraLock":   ftEnabled,
		"WinterEvent":               ftVal("false"),
		"BonfireUAVs":               ftVal("false"),
	}

	// ---- UI FEATURE GATES (S120, 2026-08-15) — ignorance-map A-14 ----------------------------
	//
	// ⚠⚠ THE FIVE KEYS ABOVE ARE FROM THE WRONG VOCABULARY, and that is why this payload has never
	// visibly done anything. MEASURED: all five are `ELokiGameFeatureToggle` ENUM MEMBER names
	// (present in the exe's enum name cluster at .rdata 0x0894B1C8–0x0894BE90; the full 149-member
	// list is tools/re/out/game_feature_toggle_enum.txt). That enum feeds
	// `ULokiGameFeatureToggles::Get(ELokiGameFeatureToggle)`, whose readiness S85 measured as
	// per-PlayerController and set at ROUND-START — not by this document.
	//
	// The UI's visibility gates call a DIFFERENT function:
	//     bool UClientConfigManager::IsFeatureEnabled(FString ToggleKey, bool bDefault)
	// keyed by STRING, read straight out of this featureToggles map. Its keys are Blueprint bytecode
	// literals in the paks and are ABSENT from the exe — "LobbyRewards" does not appear in the binary
	// at all, which is why no amount of binary scanning ever found them.
	//
	// MEASURED by exhaustive bpdump over every UFunction of the 21 assets that call it:
	// **30 bytecode call sites / 26 declared `CallFunc_IsFeatureEnabled_ReturnValue` locals / 10
	// distinct keys.** (State the unit: a local can back more than one call site.)
	//
	// ★ `bDefault` IS THE SECOND ARGUMENT and it decides whether serving a key can do anything:
	//   - bDefault=false → the surface is DARK today precisely because we omit the key; sending
	//     "true" turns it on. These are the levers.
	//   - bDefault=true  → already ON without us. Sending it can only ever turn something OFF, so
	//     **EmoteSFX, KillStreakAsRomanNumeral and voicechat are deliberately NEVER sent.**
	//
	// NOT SENT, and why:
	//   BypassTutorialAndOnboarding  bDefault=false — would SKIP onboarding. Not a surface to reveal.
	//   SeasonalBattlepass           bDefault=false — gates the EoG seasonal pass, and CLAUDE.md
	//                                records there is no packed LokiDataAsset_Season, so switching it
	//                                on invites a hard error rather than a new surface. Test alone.
	//
	// ⚠ `LobbyRewards` is AND-ed with `Array_Length(Rewards) > 0`, so the key is NECESSARY but not
	// SUFFICIENT — `Rewards` is filled by `BeginMultiClaimRewardFlow`. Serving it is what makes the
	// screen *possible*; it does not by itself make it appear. (Hero-mastery rewards are currently
	// auto-claimed natively without this widget ever activating — see docs/s120-hero-mastery.md.)
	//
	// Knob: AGS_UI_TOGGLES=0 restores the pre-S120 payload exactly, without a rebuild.
	// ★★ THE GATES ARE ALSO DECLARATIVE, and that vocabulary is FOUR TIMES bigger.
	// Besides the 10 bytecode `IsFeatureEnabled` keys, the game wraps widgets in a reusable
	// WBP_UI_ClientConfigVisbilityToggleWidget_C whose FeatureKey / ConfigKey / IsEnabledByDefault
	// are ASSET PROPERTIES — so those keys are a plain JSON property scan away and were invisible
	// to a bytecode-only census. MEASURED: **50 distinct declarative FeatureKeys** across the
	// catalog. Only the ones whose IsEnabledByDefault is absent/false are levers; the rest are
	// already ON and must never be sent false.
	//
	// ⚠ GAME DATA BUG, REPRODUCED VERBATIM BELOW: four sites declare `"ArmoryItemProgression "`
	// WITH A TRAILING SPACE (WBP_UI_Collection_ModalV2, WBP_UI_GameItemTooltip,
	// WBP_UI_RewardRoll_Base). A clean key can never satisfy them, so both spellings are served.
	// Do not "fix the typo" — the typo is in the shipped asset.
	if os.Getenv("AGS_UI_TOGGLES") != "0" {
		for _, k := range []string{
			// --- bytecode IsFeatureEnabled keys (bDefault=false) ---
			"LobbyRewards",     // multi-claim reward screen (AND-ed with Rewards.Num > 0)
			"ArmoryOnboarding", // armory FTUE highlight flow
			// --- declarative FeatureKeys with IsEnabledByDefault absent/false ---
			"exchangetokens",                  // storefront STORAGE nav (StorageConfigToggle_1)
			"storefrontcheats",                // a storefront cheat surface
			"leaderboards",                    // WBP_ProfileScreen, 2 sites
			"discord",                         // account/social/settings panels, 3 sites
			"ArmoryItemProgression",           // 7 sites
			"ArmoryItemProgression ",          // 4 sites — the shipped trailing-space key, see above
			"CosmeticEffectsOverride",         // loadout variant picker
			"DropScreenTitles",                // pre-drop screen
			"NeLobbyEventBtn",                 // lobby event button
			"ServerSelectRegionRoutes",        // region select
			"ServerSelectNetworkAcceleration", // region select
			"DebugBattlepass",                 // debug battlepass entry on the main menu

			// ---- S121 sweep, batch A: the last low-risk dark keys ----
			// A LIVE census (tools/re/toggle_readout.py) closed the declarative vocabulary exactly:
			// 50 catalog keys = 12 served + 33 IsEnabledByDefault=true (never serve) + 1 withheld
			// (BypassTutorialAndOnboarding, which REMOVES a surface) + 4 candidates. These are 3 of
			// the 4. S120 withheld them for "no backing data" — but with the readout we can now tell
			// "flag off" from "companion condition unmet", so serving them is informative rather
			// than a shot in the dark, and none of them can turn an existing surface off.
			// The 4th, SeasonalBattlepass, is deliberately NOT here — see below.
			"chuseokboostui",    // Chuseok event boost UI (2 instances)
			"prisma_boost",      // Prisma boost (2 instances)
			"lobby_survey_menu", // in-lobby survey entry (2 instances)
		} {
			featureToggles[k] = ftEnabled
		}

		// ---- ad-hoc extras, no rebuild required ----
		// AGS_UI_TOGGLES_EXTRA="a,b,c" serves additional keys as enabled. This exists so a risky
		// key can be flown ALONE, in its own attributable batch, without editing and rebuilding —
		// which is how SeasonalBattlepass should be tested:
		//
		//   SeasonalBattlepass (8 live instances) is the 4th and last candidate and is held back
		//   because CLAUDE.md records there is no packed LokiDataAsset_Season, so enabling it
		//   invites a hard error rather than a new surface. Fly it BY ITSELF with the missions
		//   page, the account pass and the news banner watched as canaries:
		//       $env:AGS_UI_TOGGLES_EXTRA = "SeasonalBattlepass"
		//
		// ⚠ Keys whose IsEnabledByDefault is true must NEVER go here — serving them can only ever
		// turn a working surface OFF. The measured never-serve list is 33 keys; see
		// TestNeverServeKeysThatAreOnByDefault.
		for _, k := range strings.Split(os.Getenv("AGS_UI_TOGGLES_EXTRA"), ",") {
			if k = strings.TrimSpace(k); k != "" {
				featureToggles[k] = ftEnabled
				extras = append(extras, k)
			}
		}

		// ---- motd: the toggle ALONE can never work — it needs a MESSAGE BODY (S121) ----
		//
		// ⚠ `motd` is the one served key whose Config carries MORE than the enable flag, which is
		// why it produced nothing when served like the others. MEASURED from the Blueprint bytecode:
		//   * `Try Show MOTD`        bails at Map_Find(Config, "key"), then requires
		//                            Config["key"] != GetMessageOfTheDayLastSeen()
		//   * `Get Message of the Day` reads Config["key"], Config["title"], Config["text"]
		//
		// So the sub-keys ARE the message: there is no separate MOTD endpoint to implement. The
		// client persists the last-seen "key" in its OWN client profile, so:
		//   ★ BUMP `key` TO RE-SHOW THE MESSAGE. An unchanged key shows once, ever, per account —
		//     which means a second launch reading "nothing happened" is EXPECTED, not a regression.
		//     Do not chase it. Change the key and it shows again.
		//
		// Knob: AGS_MOTD_KEY / AGS_MOTD_TITLE / AGS_MOTD_TEXT override the defaults;
		// AGS_MOTD=0 withholds the whole key (the pre-S121 behaviour).
		if os.Getenv("AGS_MOTD") != "0" {
			featureToggles["motd"] = map[string]any{"config": map[string]string{
				"enabled": "true",
				"default": "true",
				"key":     envOr("AGS_MOTD_KEY", "supervive-revival-motd-1"),
				"title":   envOr("AGS_MOTD_TITLE", "SUPERVIVE REVIVAL"),
				"text":    envOr("AGS_MOTD_TEXT", "This client is talking to a local community backend. Menus, missions, hunter mastery and leaderboards are served from your own machine."),
			}}
		}
	}
	// DELIBERATELY WITHHELD, with reasons:
	//   BypassTutorialAndOnboarding  would SKIP onboarding — removes a surface, does not reveal one.
	//   SeasonalBattlepass           4 sites, but CLAUDE.md records no packed LokiDataAsset_Season,
	//                                so enabling it invites a hard error. Test it ALONE.
	//   mastery                      DROPPED S121 after a LIVE MEASUREMENT. It was listed as a dark
	//                                key, but tools/re/toggle_readout.py read 3 of its 6 live widget
	//                                instances as IsEnabledByDefault=true / already enabled -- i.e.
	//                                it was ALWAYS on without us. Serving it true is a no-op, and
	//                                serving it false would REMOVE the S120 hero-mastery surfaces.
	//                                It therefore belongs with the never-send keys below.
	//   chuseokboostui, prisma_boost, lobby_survey_menu  event/survey surfaces with no backing data.
	//   EmoteSFX, KillStreakAsRomanNumeral, voicechat, and every IsEnabledByDefault=true key
	//                                (ChatLobby, CustomGameList, RankedDisplay, mailbox, XPBoosts,
	//                                EventHub, PlayerArmoryV2, party.fill, …) are ALREADY ON without
	//                                us — sending them could only ever turn something OFF.
	// ⚠ The eTag MUST move whenever the payload moves, or the client can silently keep the old
	// config. AGS_UI_TOGGLES_EXTRA changes the payload at RUNTIME, with no code edit and therefore
	// no chance to hand-bump a literal — so fold the extras into the eTag automatically. Without
	// this the knob would be a trap that quietly reproduces the exact failure mode (a stale eTag
	// over changed content) that this whole section exists to document.
	eTag := "supervive-revival-8-sweep-batchA"
	if len(extras) > 0 {
		sorted := append([]string(nil), extras...)
		sort.Strings(sorted) // stable across requests: map iteration order must not leak into the eTag
		eTag += "+x-" + strings.Join(sorted, "-")
	}
	writeJSON(w, map[string]any{
		"serviceHostnames": hostnames,
		"clientVersions": []string{
			"release2.4.live-156430-shipping",
			"release2.4.live-156430",
			"release2.4.live",
			"156430",
		},
		"featureToggles": featureToggles,
		"bannerConfigs":  bannerConfigs(base),
		// ⚠ BUMP THIS whenever the payload changes. The client is believed to only
		// *apply* a config newer/different than the one it holds; a constant eTag with
		// changed content is a plausible way to get a silent no-op. Was
		// "supervive-revival-2" for everything up to the FK-17 banner probe.
		"eTag":        eTag,
		"lastUpdated": nowISO(),
	})
}

// bannerConfigs builds ClientConfiguration.BannerConfigs — the client's own
// data-driven announcement/news system, which this project has never served.
//
// FK-17 (S119, 2026-08-13). FK-17's dead half ("SUPERVIVE.exe is a CEF/Electron
// shell") was already refuted; what survived was its **render path** question —
// whether the never-opened News / Event Hub / Referral surfaces are web pages
// impersonatable from this backend with no shim. They are reachable from here.
//
// MEASURED, from the native reflection schema (usmapdump schema.txt):
//
//	ClientConfiguration (12 props)  ... BannerConfigs  StructProperty (LokiClientBannerConfig)
//	LokiClientBannerConfig (1 prop) ... Configs        ArrayProperty<...>
//	LokiClientBannerData  (16 props):
//	    ID, FeatureToggleKey, bIsEnabledByDefault, StartTime, EndTime,
//	    BannerType   EnumProperty  -> ELokiBannerConfig_BannerType{Default=0, CustomWidget=1}
//	    WidgetType   StrProperty   (names the widget class when BannerType==CustomWidget)
//	    PrimaryText/SecondaryText/ButtonText  StructProperty(LokiBannerTextEntry{LocalizedText: TMap})
//	    PrimaryTextColor, SecondaryTextColor  StrProperty
//	    SplashImageURL, IconUrl               StrProperty   <- remote images
//	    ActionType   EnumProperty  -> ELokiBannerConfig_ActionType{Click=0, WebURL=1, DeepLink=2}
//	    ActionURL    StrProperty                            <- the web page
//
// The render targets ship in the pak (tools/extractor/out/allfiles.txt), all under
// Loki/Content/Loki/UI/Widgets/FrontEnd/MainMenu/Party/:
//
//	WBP_LobbyBannerWidgetBase, WBP_UI_LobbyBannerURL, WBP_UI_LobbyBannerURLV2,
//	WBP_UI_LobbyCarousel_LaunchBanner, BPFL_BannerConfig, EBannerConfigPlacementType
//
// and WBP_UI_LobbyCarousel_LaunchBanner is LIVE in the lobby every session — it shows
// up in LogUIActionRouter in logs going back to S52 and in the currently-running
// process. So the consumer is already on screen; only the data was missing.
//
// WHY THIS IS CHEAP TO TEST: the client polls GET /configuration/client?language=en
// every ~30 s (MEASURED in docs/capture.log: #162 19:05:27, #345 19:05:57, #529
// 19:06:27, …). So a banner change reaches an ALREADY-RUNNING client within 30 s —
// no game relaunch, no injection, no .text write. (The comment above at Register()
// saying "polled ~1/s" is stale; it is 30 s.)
//
// ★★★ THE CONSUMPTION CHAIN, DECODED FROM BYTECODE (bpdump of
// WBP_UI_PlayScreen_LobbyV2::ExecuteUbergraph + WBP_UI_LobbyCarousel_LaunchBanner).
// Read this before concluding anything from a banner that does not appear:
//
//	[10] EX_JumpIfNot( GetMissionsModel().bAllMissionLoaded )   <-- ⚠⚠ THE REAL GATE
//	[11] InitializeBanners()
//	       mgr   = GetClientBannerConfigManager(WorldContext)
//	       today = mgr->GetTodaysBannerConfig()                 // -> LokiTimespanBannerConfig
//	       LaunchBannerCarousel ->SetupFromConfig( today.Banners )       // unconditional
//	       ActivateWidget()
//	       InterstitialContainer->SetupFromConfig( today.Interstitials )
//	  then per element, in the carousel's ubergraph:
//	    [75] NotEqual_ByteByte( Config[i].BannerType, 1 )       // 1 = CustomWidget
//	    [76] EX_PopExecutionFlowIfNot(...)                      // continue only if != CustomWidget
//	    [78] BPFL_BannerConfig::"Get Content Service Asset URL from Path"( Config[i].SplashImageURL )
//	    [79] Map_Add( WebImageURLs, FullURL, Config[i].ID )     // later fetched by QueueFetchImages
//
// ⚠⚠ **`InitializeBanners` — and therefore the ENTIRE banner path — only runs when the
// MISSIONS MODEL reports `bAllMissionLoaded`.** In this project that model is populated by the
// client-side shim `missions_fix.dll`, so a `-NoHook` launch can never render a banner no matter
// how correct this payload is. MEASURED: on a clean `-NoHook` relaunch the payload deserialized
// perfectly (Configs.Num=1, all 16 fields intact) while the carousel sat with Carousel.Slots.Num=0
// and WidgetSwitcher_LoadingState.ActiveWidgetIndex=0 (parked on Overlay_Loading) — i.e.
// SetupFromConfig was never called and GetTodaysBannerConfig was never even reached.
// ⇒ **Test banners with the DEFAULT shim set (missions_fix present), never with -NoHook.**
//
// ★ The image field is NOT required to be a bare path. "Get Content Service Asset URL from Path"
// is a passthrough for absolute URLs (MEASURED, bpdump): if the string StartsWith "http://" or
// "https://" it is used verbatim with bRequiresAuth=false; otherwise it becomes
// GetServiceAddress("contentservice") + "/content-service/assets/" + <path>, with auth required.
// So the localhost URLs below are used as-is.
//
// ⚠ FK-14 caveat, and it is the one real uncertainty here: the usmap's CONTAINER
// INNER types are ~70 % wrong, and BOTH LokiClientBannerConfig.Configs and
// LokiTimespanBannerConfig.Interstitials decode as SELF-REFERENTIAL arrays — the
// textbook heap-adjacency artifact. So we do NOT know whether Configs holds
// LokiTimespanBannerConfig{FeatureToggleKey,StartTime,EndTime,Banners,Interstitials}
// or LokiClientBannerData directly.
// HEDGE: each element below carries the UNION of both structs' fields. The only
// overlapping names are FeatureToggleKey (string in both) and StartTime/EndTime
// (DateTime in both), so the union is TYPE-SAFE under either reading — and per the
// validity model (see server/internal/menu/menu.go) UE's JsonObjectStringToUStruct
// ignores unknown keys and rejects only a MATCHED key with a wrong type. This is a
// hedge against instrument uncertainty, not a bundled multi-hypothesis test: the
// single hypothesis is "banner data served here reaches the lobby banner widget".
func bannerConfigs(base string) map[string]any {
	// Wide-open window: the record is scheduled by StartTime/EndTime, so a banner
	// outside its window is indistinguishable from a banner that never parsed.
	const start = "2020-01-01T00:00:00Z"
	const end = "2099-12-31T23:59:59Z"

	// LokiBannerTextEntry{ LocalizedText: TMap }. The key is a culture code — the
	// request is ?language=en — but the exact key form is unverified, so serve
	// several. Extra map keys are values, not schema, so this cannot cause a reject.
	text := func(s string) map[string]any {
		return map[string]any{"localizedText": map[string]string{
			"en": s, "en-US": s, "default": s, "": s,
		}}
	}

	banner := map[string]any{
		"id":               "revival-fk17-banner",
		"featureToggleKey": "", // empty => ungated; bIsEnabledByDefault decides
		// UE's JSON converter may or may not strip the leading 'b' of a bool
		// UPROPERTY. Serve both spellings — the unmatched one is ignored for free.
		"bIsEnabledByDefault": true,
		"isEnabledByDefault":  true,
		"startTime":           start,
		"endTime":             end,
		// Enum values go over the wire as the enumerator NAME. (S118's userStatusNotif
		// lesson: a wrong enum string sinks the whole struct — and LogJson echoes the
		// rejected value and names the property + enum, so WATCH LogJson on this run.)
		"bannerType":         "Default",
		"widgetType":         "",
		"primaryText":        text("SUPERVIVE REVIVAL"),
		"secondaryText":      text("Backend is live. This banner came from the local server."),
		"buttonText":         text("OPEN"),
		"primaryTextColor":   "#FFFFFF",
		"secondaryTextColor": "#C8C8C8",
		// ⚠⚠ THE ?v= IS AN INSTRUMENT, NOT DECORATION — DO NOT REMOVE IT.
		// The client CACHES banner images to %LOCALAPPDATA%\SUPERVIVE\Saved\ImageCaches
		// (see ImageCacheIndex.json, which after the first render contains exactly
		// "http://localhost:8080/revival/banner/splash.png"). Once cached, the banner draws
		// with NO HTTP REQUEST AT ALL — so "no splash fetch in docs/capture.log" stops meaning
		// "the banner did not render" and starts meaning nothing whatsoever. That null was
		// briefly read as a regression on 2026-08-14.
		// bannerAssetNonce changes once per ags start, so each RUN takes exactly one cache miss
		// per image: a splash fetch in the capture is then real, positive evidence that the
		// carousel populated, and its ABSENCE is interpretable again. Within a run the URL is
		// stable, so the client's cache still works normally.
		"splashImageURL": base + "/revival/banner/splash.png?v=" + bannerAssetNonce,
		"iconUrl":        base + "/revival/banner/icon.png?v=" + bannerAssetNonce,
		// The FK-17 payoff: if this is honoured, the client hands a URL to a web view.
		"actionType": "WebURL",
		"actionURL":  base + "/revival/banner/news.html",
	}

	// ★ THE UNION HEDGE IS RESOLVED — MEASURED, and the hedge worked exactly as designed.
	// A read-only walk of the LIVE heap (PID 60260) through offsets resolved BY NAME showed
	// the client materialized the TIMESPAN reading:
	//   ClientConfiguration.BannerConfigs.Configs   Num=1  (MergedConfiguration likewise 1;
	//                                                       OverrideConfiguration coherently unset)
	//   element = LokiTimespanBannerConfig, stride 64  (last prop Interstitials @+0x30 +16 = 0x40)
	//   .Banners  Num=1, element = LokiClientBannerData, stride 408 (ActionURL @+0x188 +16 = 0x198)
	//   all 16 banner fields intact, StartTime/EndTime parsed to real FDateTime ticks,
	//   ActionType = 1 = WebURL, BannerType = 0 = Default, each LocalizedText TMap Num=4.
	// Controls in the same walk: ETag read back our string, ClientVersions 4, ServiceHostnames 26,
	// FeatureToggles 5 — so the numbers are statements about the data, not about the walk.
	// ⇒ the 16 LokiClientBannerData keys the hedge copied to the element's top level are provably
	// inert, and are dropped here so future banner tests stay single-variable.
	//
	// ★★ REUSABLE FK-14 WORKAROUND, worth remembering: where the usmap's container inner type is
	// untrustworthy, serve a TYPE-SAFE UNION of the candidate structs, then read the live heap to
	// see which reading the client materialized. The element STRIDE plus the FProperty chain
	// identify the struct that the usmap could not. That is how this was settled — not by trusting
	// either schema dump, which disagreed with each other exactly as FK-14 predicts.
	//
	// The correct inner type, MEASURED live via the FK-14-correct offsets
	// (FArrayProperty::Inner = *(field+0x78), then FStructProperty::Struct = *(inner+0x70)):
	//     LokiClientBannerConfig.Configs  ->  TArray<LokiTimespanBannerConfig>
	//     LokiTimespanBannerConfig.Banners ->  TArray<LokiClientBannerData>
	// The second is independently corroborated from BYTECODE: WBP_UI_PlayScreen_LobbyV2's
	// InitializeBanners passes GetTodaysBannerConfig().Banners straight into the carousel's
	// SetupFromConfig(Config: TArray), whose loop does Array_Get(Config, i) and then reads
	// item.BannerType / item.SplashImageURL / item.ID — i.e. banner RECORDS, not ID strings.
	elem := map[string]any{
		"featureToggleKey": "",
		"startTime":        start,
		"endTime":          end,
		"banners":          []any{banner},
		// LokiClientBannerConfigManager.bHasSeenInterstitial implies a full-screen
		// interstitial path (WBP_UI_Interstitial_Container also takes SetupFromConfig).
		// Left empty so this probe stays about the in-lobby banner only.
		"interstitials": []any{},
	}

	return map[string]any{"configs": []any{elem}}
}

// --- FK-17 banner probe assets -------------------------------------------------
//
// These exist so the banner probe is self-contained and, crucially, so each stage
// of it leaves its OWN receipt in docs/capture.log. Three independent signals:
//
//	GET /revival/banner/splash.png  => the banner record parsed AND the widget is
//	                                   resolving its images (strongest single receipt:
//	                                   the client only fetches a URL it actually read
//	                                   out of our JSON)
//	GET /revival/banner/icon.png    => same, second field
//	GET /revival/banner/news.html   => the banner was CLICKED and ActionType==WebURL
//	                                   was honoured — i.e. a menu surface really is a
//	                                   web page we control, which is FK-17's whole point
//
// ⚠ Do not read a missing news.html fetch as a negative: it requires a human click.
// The image fetches are the automatic ones.
func solidPNG(c color.RGBA, w, h int) []byte {
	img := image.NewRGBA(image.Rect(0, 0, w, h))
	draw.Draw(img, img.Bounds(), &image.Uniform{c}, image.Point{}, draw.Src)
	var buf bytes.Buffer
	_ = png.Encode(&buf, img)
	return buf.Bytes()
}

var (
	bannerSplashPNG = solidPNG(color.RGBA{R: 0x1E, G: 0x2A, B: 0x4A, A: 0xFF}, 512, 256)
	bannerIconPNG   = solidPNG(color.RGBA{R: 0xE8, G: 0x6A, B: 0x17, A: 0xFF}, 64, 64)

	// bannerAssetNonce is stamped into the banner image URLs as ?v=<nonce>. It changes once
	// per ags start and is CONSTANT within a run — see the comment at splashImageURL for why
	// this exists (it is what keeps "did the banner render?" answerable at all, given the
	// client's on-disk image cache). Seconds granularity is plenty: the only requirement is
	// that a fresh ags produces a URL the client has not already cached.
	bannerAssetNonce = strconv.FormatInt(time.Now().Unix(), 10)
)

func writePNG(w http.ResponseWriter, b []byte) {
	w.Header().Set("Content-Type", "image/png")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(b)
}

func (s *Service) handleBannerSplash(w http.ResponseWriter, r *http.Request) {
	writePNG(w, bannerSplashPNG)
}

func (s *Service) handleBannerIcon(w http.ResponseWriter, r *http.Request) {
	writePNG(w, bannerIconPNG)
}

// handleBannerPage is the ActionURL target. If this is ever fetched, the client
// rendered or opened a page we authored — which is exactly the capability FK-17
// predicted and which needs no DLL injection at all.
func (s *Service) handleBannerPage(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(`<!doctype html><meta charset="utf-8">
<title>SUPERVIVE Revival</title>
<style>
  html,body{margin:0;height:100%;background:#12182b;color:#f2f4f8;
    font:16px/1.5 "Segoe UI",system-ui,sans-serif;display:grid;place-items:center}
  .c{text-align:center;padding:2rem}
  h1{margin:0 0 .5rem;font-size:2rem;letter-spacing:.08em}
  p{margin:.25rem 0;color:#9fb0cc}
  code{color:#e86a17}
</style>
<div class="c">
  <h1>SUPERVIVE REVIVAL</h1>
  <p>This page was served by the local Go backend.</p>
  <p>If you can read this inside the game, <code>ActionType: WebURL</code> works
     and the menu web surface is ours.</p>
</div>`))
}

func nowISO() string { return time.Now().UTC().Format("2006-01-02T15:04:05Z") }

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(v)
}
