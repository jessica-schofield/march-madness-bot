            try:
                if pool.get("MEN_URL"):
                    top_men = run_async(get_top_n_async(pool["MEN_URL"], config.get("TOP_N", 5), PLAYWRIGHT_STATE))
            except Exception as e:
                print(f"[WARN] Failed to fetch men's leaderboard: {e}")
                if manager_id:
                    send_dm(manager_id, f"⚠️ Couldn't scrape the men's leaderboard:\n