# EDH Tracker – Database Models

This document outlines the database schema for storing EDH game information using a relational (SQL) database. The schema is designed to capture:

- **Pods** (groups of players)
- **Players** (users, identified by their Telegram IDs or another unique ID)
- **Pod Membership** (which players belong to which pods)
- **Games** (metadata for each game, such as creation time and finalized status)
- **Game Results** (which players participated in each game and their outcomes)
- **Eliminations** (optional table to record which player eliminated which other player in a game)
- **Game Deletion Requests** (requests to delete games)

## Table of Contents

1. [Pods](#pods)
2. [Players](#players)
3. [Pods Players](#pods_players)
4. [Games](#games)
5. [Game Results](#game_results)
6. [Eliminations](#eliminations)
7. [Game Deletion Requests](#game_deletion_requests)
8. [Relationships and ER Diagram](#relationships)
9. [Example Queries](#example-queries)

---

## 1. Pods

**Table Name:** `pods`

| Column     | Type         | Constraints               | Description                                         |
|------------|-------------|---------------------------|-----------------------------------------------------|
| `pod_id`   | `INT`       | **PRIMARY KEY**           | Unique identifier for each pod.                     |
| `name`     | `VARCHAR`   | **NOT NULL**              | Name of the pod.                                    |

**Description**  
The `pods` table stores metadata about each EDH pod (i.e., a group of players). A row in this table corresponds to one pod, which may contain multiple players.

---

## 2. Pods Players

**Table Name:** `pods_players`

| Column           | Type         | Constraints                             | Description                                                                                                 |
|------------------|-------------|-----------------------------------------|-------------------------------------------------------------------------------------------------------------|
| `pods_player_id` | `INT`       | **PRIMARY KEY**, auto-increment (or UUID) | A unique surrogate key for referencing this membership row in other tables (e.g., game results).           |
| `pod_id`         | `INT`       | **FOREIGN KEY** → `pods(pod_id)`, **NOT NULL** | The ID of the pod. This links which pod the player is associated with.                                      |
| `telegram_id`    | `BIGINT`    | **NOT NULL**                            | The user’s global Telegram ID (or any global unique user ID).                                               |
| `name`           | `VARCHAR`   | **NOT NULL**                            | The display name for this user **within this pod**.                                                         |
| `avatar_url`     | `VARCHAR`   | Nullable                                | An optional URL pointing to this player’s avatar (pod-specific if you like).                                |

**Description**  
Each row represents **one user’s membership in one pod**. We want each player’s name (and avatar) to be **pod-specific** so we store these attributes here. A user in multiple pods will have multiple rows (one per pod).

> **Note:** `telegram_id` is not a foreign key here since we’ve removed the global `players` table. If you want to keep a reference to a more global “user record,” you could still do that. But per requirements, we now hold all relevant info in `pods_players`.

---

## 3. Games

**Table Name:** `games`

| Column               | Type         | Constraints                              | Description                                       |
|---------------------|-------------|------------------------------------------|---------------------------------------------------|
| `game_id`           | `INT`       | **PRIMARY KEY**, auto-increment          | Unique identifier for each game.                  |
| `pod_id`            | `INT`       | **FOREIGN KEY** → `pods(pod_id)`, **NOT NULL**, **INDEXED** | The ID of the pod in which the game took place.   |
| `created_at`        | `DATETIME`  | **NOT NULL**, **INDEXED**                | When the game was created (UTC).                  |
| `deletion_reference`| `VARCHAR`   | **UNIQUE**                               | Reference code for game deletion requests.        |

**Description**  
This table holds general metadata for each game: which pod it belongs to, when it was created, and a unique reference for deletion requests. The `pod_id` and `created_at` columns are indexed for efficient querying of game history and leaderboards.

---

## 4. Game Results

**Table Name:** `game_results`

| Column       | Type                           | Constraints                                                       | Description                                                                              |
|--------------|--------------------------------|-------------------------------------------------------------------|------------------------------------------------------------------------------------------|
| `game_id`    | `INT`                          | **FOREIGN KEY** → `games(game_id)`, **PRIMARY KEY** (composite)   | The ID of the game.                                                                      |
| `player_id`  | `INT`                          | **FOREIGN KEY** → `pods_players(pods_player_id)`, **PRIMARY KEY** (composite) | The ID of the player who participated in the game.                                       |
| `outcome`    | `VARCHAR`                      | **NOT NULL**                                                      | The result for this player in the game ('win', 'lose', or 'draw').                      |

**Description**  
`game_results` captures the relationship between a game and each participating player. The `outcome` is stored as a VARCHAR with three possible values: 'win', 'lose', or 'draw'. A future enhancement may migrate this to use a proper ENUM type.

---

## 5. Eliminations

**Table Name:** `eliminations`

| Column           | Type   | Constraints                                                                              | Description                                                        |
|------------------|--------|------------------------------------------------------------------------------------------|--------------------------------------------------------------------|
| `elimination_id` | `INT`  | **PRIMARY KEY**, auto-increment                                                           | Unique identifier for each elimination.                             |
| `game_id`        | `INT`  | **FOREIGN KEY** → `games(game_id)`, **NOT NULL**                                         | The ID of the game.                                                |
| `eliminator_id`  | `INT`  | **FOREIGN KEY** → `pods_players(pods_player_id)`, **NOT NULL**                           | The player who eliminated someone.                                 |
| `eliminated_id`  | `INT`  | **FOREIGN KEY** → `pods_players(pods_player_id)`, **NOT NULL**                           | The player who was eliminated.                                     |

**Description**  
This table records specific elimination events in games, tracking who eliminated whom. Each row represents one player eliminating another player in a specific game.

---

## 6. Game Deletion Requests

**Table Name:** `game_deletion_requests`

| Column         | Type      | Constraints                                                                              | Description                                                        |
|----------------|-----------|------------------------------------------------------------------------------------------|-------------------------------------------------------------------|
| `request_id`   | `INT`     | **PRIMARY KEY**, auto-increment                                                           | Unique identifier for each deletion request.                        |
| `game_id`      | `INT`     | **FOREIGN KEY** → `games(game_id)`, **NOT NULL**, ON DELETE CASCADE                      | The game to be deleted.                                            |
| `requester_id` | `INT`     | **FOREIGN KEY** → `pods_players(pods_player_id)`, **NOT NULL**, ON DELETE CASCADE        | The player requesting deletion.                                     |
| `created_at`   | `DATETIME`| **NOT NULL**                                                                             | When the deletion request was created (UTC).                        |

**Description**  
This table tracks requests to delete games. Multiple players can request deletion of the same game. The CASCADE delete ensures that deletion requests are automatically removed if either the game or the requesting player is deleted.

---

## 7. Relationships and ER Diagram

### Relationship Summary
- **Pod** to **PodPlayer** to **Player** is a many-to-many relationship between `pods` and `players`.
- **Game** belongs to a **Pod** (`pod_id` is a foreign key in `games`).
- **Game** to **GameResult** to **Player** is a many-to-many relationship describing which players participated in which game, and with what result.
- **Elimination** is effectively an intersection linking a specific `game_id` and two different `players`: the eliminator and the eliminated.
- **Game Deletion Request** is a request to delete a game, linked to the game and the requesting player.

### Conceptual ER Diagram

```
+-----------+              
|   pods    |              
|-----------|              
| pod_id PK |          
| name      |              
+-----^-----+              
      |                    
      |        +----------------------------------+
      +--------| pods_players                      |
               |----------------------------------|
               | pods_player_id PK (auto-increment)|
               | pod_id  (FK -> pods)             |
               | telegram_id                      |
               | name                             |
               | avatar_url                       |
               +---------------^-------------------+
                               |
 +-----------+                 |
 |   games   |                 |
 |-----------|                 |
 | game_id PK|-----+           |
 | pod_id FK |     |           |
 | created_at|     |           |
 | deletion_ref    |           |
 +------^----+     |           |
        |          |           |
        |   +-----------+      |
        +---| game_results|<---+
            |----------- |
            | game_id  (FK), PK (composite)
            | pods_player_id (FK), PK (composite)
            | outcome (varchar)
            +-------------+


 +--------------------------------------------------+
 |                    eliminations                   |
 |--------------------------------------------------|
 | elimination_id PK (auto-increment)                |
 | game_id (FK)                                     |
 | eliminator_id (FK -> pods_players)               |
 | eliminated_id (FK -> pods_players)               |
 +--------------------------------------------------+

 +--------------------------------------------------+
 |               game_deletion_requests              |
 |--------------------------------------------------|
 | request_id PK (auto-increment)                   |
 | game_id (FK -> games, cascade)                   |
 | requester_id (FK -> pods_players, cascade)       |
 | created_at                                       |
 +--------------------------------------------------+
```

---

## 8. Example Queries <a name="example-queries"></a>

### 8.1. Create a Pod

```sql
INSERT INTO pods (pod_id, name)
VALUES (1, 'Fun Pod');
```

### 8.2. Add a Player to a Pod

Suppose a user with Telegram ID `123456789` joins pod `1`. They choose the name “Alice” in that pod, and we store an avatar URL:

```sql
INSERT INTO pods_players (pod_id, telegram_id, name, avatar_url)
VALUES (1, 123456789, 'Alice', 'https://example.com/alice.png');
```

The database will assign an auto-increment (or generated) `pods_player_id`. For example, it might be `42`.

### 8.3. Create a Game

```sql
INSERT INTO games (game_id, pod_id, created_at, deletion_reference)
VALUES (10, 1, '2025-01-03 12:00:00', 'abc123');
```

### 8.4. Record Outcomes

Let’s say pods_player_id `42` (Alice) won, pods_player_id `43` (Bob) lost:

```sql
INSERT INTO game_results (game_id, player_id, outcome)
VALUES
  (10, 42, 'win'),
  (10, 43, 'lose');
```

### 8.5. Optional Detailed Eliminations

If you want to record who eliminated whom:

```sql
INSERT INTO eliminations (game_id, eliminator_id, eliminated_id)
VALUES 
  (10, 42, 43);  -- Bob was eliminated by Alice
```

### 8.6. Request Game Deletion

```sql
INSERT INTO game_deletion_requests (game_id, requester_id, created_at)
VALUES (10, 42, '2025-01-03 12:05:00');
```

### 8.7. Finalize the Game

```sql
UPDATE games
SET deletion_reference = NULL
WHERE game_id = 10;
```

### 8.8. Query Player Stats Within a Pod

For instance, to get total wins, losses, draws, and kills for each player in `pod_id = 1`:

```sql
SELECT
  pp.pods_player_id,
  pp.name,
  pp.avatar_url,
  SUM(CASE WHEN gr.outcome = 'win' THEN 1 ELSE 0 END) AS total_wins,
  SUM(CASE WHEN gr.outcome = 'lose' THEN 1 ELSE 0 END) AS total_losses,
  SUM(CASE WHEN gr.outcome = 'draw' THEN 1 ELSE 0 END) AS total_draws,
  COUNT(*) AS games_played
FROM game_results gr
JOIN games g
  ON gr.game_id = g.game_id
JOIN pods_players pp
  ON gr.player_id = pp.pods_player_id
WHERE g.pod_id = 1
GROUP BY pp.pods_player_id, pp.name, pp.avatar_url;
```

---

## Summary

- **`pods`**: Defines each pod.  
- **`pods_players`**: One row per user-per-pod, storing pod-specific info like display name and avatar URL.  
- **`games`**: One record per game, referencing the pod it belongs to.  
- **`game_results`**: Ties each game to the participants (`pods_player_id`), including their outcome (win/lose/draw).  
- **`eliminations`** (optional): If you need a detailed record of who eliminated whom.  
- **`game_deletion_requests`**: Tracks requests to delete games.

This design should cleanly map onto the existing code structure (where `Pod`, `PlayerStats`, and `Game` are separate concepts).
