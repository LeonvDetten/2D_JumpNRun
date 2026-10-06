# Daten für den Neustart-Arm (Stand Phase 10, 06.10. 08:30 UTC)

Entpacken im Repo-Wurzelverzeichnis: `tar -xJf daten_neustart/runs_phase10_daten.tar.xz`

| Datei | Inhalt |
|---|---|
| `runs/demos10/demos.jsonl` | 2090 Lehrer-Beispiele auf Übungsleveln (7 Arten, d0–d2, Seed-Raum `demo10:`, Löser mit 7 Aktionen) |
| `runs/demos10/holdout.jsonl` | 233 zurückgehaltene Lehrer-Beispiele (nie trainieren, nur messen) |
| `runs/demos9/demos.jsonl` | 283 Phase-9-Lehrer-Beispiele (Kanal, Umkehren, Spiegel, Sackgasse) |
| `runs/demos4/demos.jsonl` + `pool.json`, `runs/demos/*.jsonl` | Phase-7/8-Demos (BC1, Pool, Mitte-Starts) |
| `runs/phase10/anchor_states.npz` | 12 020 Zustände gewonnener P8-Episoden + P8-Wahrscheinlichkeiten |
| `runs/phase10/kl_states.npz` | Drift-Zustände (KL zu P8) |
| `runs/phase10/a6_states.npz` | 489 reine links+springen-Zustände (Startprüfung) |
| `runs/phase10/*.json` | Ausgangswerte (P8, Startmodell, …), Wächter-Kalibrierung, Autopilot-Zustand |
| `runs/phase10_*/milestones10.json`, `drift.json` | alle Messkurven der Runden A, B, C (Stand 08:30) |

Caches (`dataset_ppo_ov3.npz`, `bc2_*.npz`) sind nicht enthalten. Sie werden beim ersten Gebrauch neu gebaut;
der BC2-Cache braucht etwa 20–30 min auf einem Kern.
