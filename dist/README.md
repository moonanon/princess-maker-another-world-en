# Princess Maker: Legend of Another World, English patches

Three patches. Pick **one** and apply it to the unmodified Japanese ROM (do not stack them):
*Princess Maker - Legend of Another World (Japan).sfc*, 2 MiB, no copier header, md5 `135ad0c718e88aaa9de9ce848b47753a`.

| Patch | What you get |
| --- | --- |
| `princess-maker-en.ips` | The English translation. The game plays exactly as the original. |
| `princess-maker-en-bugfix.ips` | The translation + fixes for the original game's own bugs. |
| `princess-maker-en-questing.ips` | The translation + the bug fixes + a reworked Quest. |

## Bug fixes (`-bugfix` and `-questing`)

- **The demon deal** (a quest cave): signing his contract outright no longer pays out a leftover sum of gold, and once
  she has signed, the demon never appears again (the original reset its flag every month). Signing for his 500 or
  1000 Gold still gives the gold and the contract, as in the original.
- **The jester**: after his farewell he is gone from the castle, instead of still being visitable there.
- **The Demon King's proposal**: in the hero ending where she slays the Demon King, he no longer turns up afterwards
  to ask for her hand.
- **The young dragon's proposal**: when the young dragon and his grandfather come to ask for her hand and you answer
  **Allow It**, he now comes back for her at the end, as he promises. In the original nothing ever recorded your answer,
  so his marriage ending could never happen. Answering **Refuse** works as before.

## Questing (`-questing` only)

- **Going home early** from a quest raises her warrior/magic rating by the days she was actually out. The original gives
  every scheduled day (a 10-day quest abandoned on day 2 still gives +10), which is a free rating exploit; `-bugfix`
  keeps it for players who like it.
- Defeating a peaceful person (traveller, mage, soldier) in a quest battle costs 30 Morality, the game's own
  penalty. Bandits, kidnappers and outlaws can still be fought freely.
- Asking a peaceful person for nothing never starts a fight (the original could, even after a friendly talk).
- When you talk to someone, the approach menu lists Smile first, so the cursor starts on the friendly choice.
- Taking a peaceful person's life when they give in to your demand costs the same 30 Morality. A refused demand
  still ends in a fight, as in the original.
