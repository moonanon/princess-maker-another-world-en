# Endings and how to reach them

> **Spoilers.** This lists every ending and what decides it. Part of the fun of a Princess Maker game is finding
> out what your daughter becomes without knowing the rules. If you haven't finished a playthrough yet, consider
> coming back later.

Everything here was read from the game's own code.

The game decides three things when she turns 18:

1. **Her career** (which ending plays).
2. **How well it went**: each ending has three epilogues, from great to poor, picked by one stat against two marks.
3. **Whom she marries**, separately from the career (see [Marriage](#marriage)).

## Stats used here

Base stats: Vigor, Might, Intellect, Grace, Charm, Morality, Faith, Sin, Sensitivity.
Reputations: Warrior, Magic, Social, Domestic. Skills: Combat ... Speech, Art (as on the status screen).

### Hidden values

A few things the endings check never show on the status screens:

| Hidden value | What raises it |
| --- | --- |
| **Popularity** | pleasant chats with people at the castle; each one adds an amount based on her Grace |
| **Jester talks** | each good conversation with the jester at the castle |
| **Painting and dance lessons** | how many times she has taken each class |
| **The castle suitor's affection** | the young man at the castle, raised by visiting him |
| **Father's affection** | her bond with her father; it fades a little every month |
| **Raphael's affection** | her bond with Raphael, the butler |
| **Galbar's event** | meeting the Demon King Galbar in his story event |
| **The young dragon's promise** | answering Allow It when the young dragon visits |

## Step 1: which branch

The game checks these in order and takes the first that fits:

| # | Branch | When |
| --- | --- | --- |
| 1 | **Wicked** | Morality = 0 and Sin ≥ 120, or Morality < 30 and Sin ≥ 200 |
| 2 | **Artist** | her highest skill is Art, and Art ≥ 128 |
| 3 | **Well-rounded** | her highest reputation is less than 50 above her lowest |
| 4 | **Warrior** | Warrior is her highest reputation |
| 5 | **Mage** | Magic is her highest reputation |
| 6 | **Social, spoken for** | Social is highest **and** one of the special husbands wants her (see Marriage) |
| 7 | **Homemaker** | anything else (Domestic highest, or Social highest with no special suitor) |

Inside most branches, her **highest reputation** sets a tier: **A** ≥ 400, **B** 350-399, **C** 250-349,
**D** 150-249, **E** under 150.

## Step 2: the ending

### 1. Wicked

| Ending | Needs |
| --- | --- |
| 96 Demon King | Sin ≥ 500, Warrior ≥ 300, Magic ≥ 200 |
| 90 Underworld boss | Warrior ≥ 200, Sin ≥ 200, Grace ≥ 200 |
| 94 Swindler | Warrior < 200, Speech ≥ 70, Sensitivity < 100 |
| 92 Thug | anything else |

### 2. Artist

| Ending | Needs |
| --- | --- |
| 86 Jester | Speech ≥ 80 and at least 21 good talks with the jester |
| 88 Painter | more painting lessons than dance lessons |
| 102 Dancer | otherwise |

### 3. Well-rounded

| Tier | Ending |
| --- | --- |
| A | **0 Queen** (the King hands her the throne) if Grace ≥ 700 and Popularity ≥ 600; else **2 Chancellor** |
| B | the highest of Intellect / Morality / Faith: Faith → **4 Cardinal**, Morality → **6 Minister**, Intellect → **8 Royal scholar** |
| C | the same: Faith → **10 Nun**, Morality → **12 Royal judge**, Intellect → **14 Academy researcher** |
| D, E | **her job**: the job she worked most, if she worked it at least 10 times (table below); else **56 Homemaker** |

Job endings (tier D: she runs or rises in the trade; tier E: she goes back to it part-time):

| Job she worked most | Tier D | Tier E |
| --- | --- | --- |
| Church | 18 | 38 |
| Tailor | 28 | 44 |
| Farm | 16 | 36 |
| Diner | 20 | 40 |
| Hairdresser | 22 | 42 |
| Smithy | 26 | 46 |
| Gravekeeper | 24 | 48 |
| Dancer | 32 | 52 |
| Tutor | 30 | 50 |
| Gladiator | 98 | 100 |
| Chores or the Grand Salon | 34 Grand Salon | 54 Grand Salon |

### 4. Warrior

| Tier | Ending |
| --- | --- |
| A | **58 Hero** (she sets out on a journey) if Sensitivity ≥ 250 and Morality ≥ 50; else **66 Bounty hunter** |
| B | **60 General** if Intellect ≥ 200; else **62 Royal Guard knight** |
| C | **62 Royal Guard knight** if Grace ≥ 150; else **66 Bounty hunter** |
| D, E | **64 Gladiator** if Sin ≥ 30; else **66 Bounty hunter** |

### 5. Mage

| Tier | Ending |
| --- | --- |
| A | **68 Wandering mage** if Sensitivity ≥ 250 and Morality ≥ 50; else **72 Sorceress** |
| B | **70 Court mage** if Intellect ≥ 250 and Popularity ≥ 300; else **72 Sorceress** |
| C | **72 Sorceress** if Morality ≥ 50; else **74 Fortune-teller** |
| D | **74 Fortune-teller** |
| E | **76 Stage magician** |

### 6. Social, spoken for

| Tier | Ending |
| --- | --- |
| A | **78 Queen consort** (the King proposes) |
| B | **80 Countess** |
| C | **82 Lady of society** |
| D, E | **84 The rich man's wife** |

### 7. Homemaker

**56 Homemaker**: she waits at home for the right person.

## Marriage

After the career ending, the epilogue names her husband. The first of these she qualifies for wins:

| Husband | Needs |
| --- | --- |
| The young man from the castle | his affection ≥ 90, Charm ≥ 200, Grace ≥ 250, Morality ≥ 50, Sin < 50 |
| Her father | his affection ≥ 100, Morality ≥ 100, Faith ≥ 100, Sin < 50 |
| Raphael, the butler | his affection ≥ 100, Charm ≥ 200, Sensitivity ≥ 250 |
| Galbar, the Demon King | his event done, Charm ≥ 300, Grace ≥ 200, Sin at least twice her Morality |
| The young dragon | his promise (only with the bug-fix/questing patches: his marriage *cannot* be triggered in the original game) |

Without any of them she marries a generic man that's described based on her Morality and whether Charm ≥ 200.

## How to aim (and how to avoid an ending)

- **The branch comes first.** Stats only matter inside the branch she lands in, so decide which reputation should
  lead. Fighting quests and bounties raise Warrior quickly, and once it leads, Etiquette and Grace won't change
  the career (only the tier checks above).
- **To stay out of the Warrior or Mage branch**, keep all four reputations within 50 of each other
  (Well-rounded), or put Social or Domestic on top.
- **Thresholds, not totals.** Each check is a mark; going far past it does nothing more.
