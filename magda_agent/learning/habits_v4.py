import logging
import uuid
import time
from typing import Optional
from collections import Counter

from magda_agent.learning.habits import HabitTracker


class HabitTrackerV4(HabitTracker):
    """
    HabitTrackerV4 introduces momentum-based explicit time decay to learned habits.
    Habit weights decay over time, and frequently used habits gain momentum (weight).
    """

    def record_usage(self, input_text: str, skill_used: str, evaluation_score: float, user_id: int = None) -> None:
        """
        Records the successful usage of a skill. Assigns an initial weight (momentum).

        Args:
            input_text (str): The user's input.
            skill_used (str): The name of the skill that was used.
            evaluation_score (float): The evaluation score of the response.
            user_id (int, optional): The ID of the user.
        """
        if evaluation_score >= 8.0:
            try:
                habit_id = str(uuid.uuid4())
                metadata = {
                    "skill_used": skill_used,
                    "timestamp": time.time(),
                    "weight": 1.0  # Initial momentum/weight
                }
                if user_id is not None:
                    metadata["user_id"] = user_id

                self.collection.add(
                    documents=[input_text],
                    metadatas=[metadata],
                    ids=[habit_id]
                )
                logging.info(f"HabitV4 reinforced: Stored success for skill '{skill_used}' with initial momentum.")
            except Exception as e:
                logging.error(f"Failed to record habit V4: {e}")

    def decay_habits_with_momentum(self, decay_rate: float = 0.1, min_weight: float = 0.2) -> int:
        """
        Applies explicit time decay to habit weights based on elapsed days.
        If a habit's weight falls below `min_weight`, it is removed.

        Args:
            decay_rate (float): The rate at which the weight decays per day.
            min_weight (float): The threshold below which a habit is deleted.

        Returns:
            int: The number of habits decayed and removed.
        """
        try:
            current_time = time.time()
            results = self.collection.get(include=["metadatas"])
            if not results or not results.get("ids"):
                return 0

            ids_to_delete = []
            ids_to_update = []
            metadatas_to_update = []

            for i, meta in enumerate(results["metadatas"]):
                if meta and "timestamp" in meta:
                    record_time = meta["timestamp"]
                    current_weight = meta.get("weight", 1.0)

                    elapsed_seconds = current_time - record_time
                    elapsed_days = elapsed_seconds / (24 * 3600)

                    # Momentum-based decay: e.g., weight = weight - (decay_rate * elapsed_days)
                    # or linear decay based on days passed since last update
                    new_weight = current_weight - (decay_rate * elapsed_days)

                    if new_weight < min_weight:
                        ids_to_delete.append(results["ids"][i])
                    else:
                        # Only update if the weight actually changed significantly (or just update timestamp)
                        if new_weight != current_weight:
                            meta["weight"] = new_weight
                            # We can also reset the timestamp so decay doesn't over-accumulate
                            meta["timestamp"] = current_time
                            ids_to_update.append(results["ids"][i])
                            metadatas_to_update.append(meta)

            if ids_to_delete:
                self.collection.delete(ids=ids_to_delete)
                logging.info(f"Decayed and removed {len(ids_to_delete)} habits due to low momentum.")

            if ids_to_update:
                # ChromaDB collection update method signature usually takes ids and metadatas
                self.collection.update(ids=ids_to_update, metadatas=metadatas_to_update)
                logging.info(f"Updated momentum for {len(ids_to_update)} habits.")

            return len(ids_to_delete)

        except Exception as e:
            logging.error(f"Failed to decay habits with momentum: {e}")
            return 0

    def suggest_strategy(self, input_text: str, user_id: int = None) -> Optional[str]:
        """
        Suggests a strategy taking into account momentum/weights of the found habits.

        Args:
            input_text (str): The user's input.
            user_id (int, optional): The ID of the user.

        Returns:
            Optional[str]: Suggested skill name.
        """
        try:
            if self.collection.count() == 0:
                return None

            query_kwargs = {
                "query_texts": [input_text],
                "n_results": min(10, self.collection.count())
            }
            if user_id is not None:
                query_kwargs["where"] = {"user_id": user_id}

            results = self.collection.query(**query_kwargs)

            if not results or not results.get("distances") or not results["distances"][0]:
                return None

            distances = results["distances"][0]
            metadatas = results["metadatas"][0]

            distance_threshold = 1.0

            # Aggregate weights for skills
            skill_weights = {}
            for dist, meta in zip(distances, metadatas):
                if dist < distance_threshold and meta and "skill_used" in meta:
                    skill = meta["skill_used"]
                    weight = meta.get("weight", 1.0)
                    skill_weights[skill] = skill_weights.get(skill, 0.0) + weight

            if not skill_weights:
                return None

            # Find the skill with the highest aggregated weight
            best_skill = max(skill_weights.items(), key=lambda x: x[1])

            # The base HabitTracker required max_count >= 2. Here we might require a cumulative weight threshold.
            if best_skill[1] >= 1.5:  # e.g., equivalent to approx 2 usages with some decay
                logging.info(f"HabitV4 matched: Suggesting skill '{best_skill[0]}' with momentum weight {best_skill[1]:.2f}.")
                return best_skill[0]

            return None
        except Exception as e:
            logging.error(f"Failed to suggest strategy in V4: {e}")
            return None
