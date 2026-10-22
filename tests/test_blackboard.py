"""Tests for the Blackboard context system."""

import asyncio
import tempfile
import unittest
from pathlib import Path
from antigrvity.core.context import Blackboard


class TestBlackboard(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.blackboard = Blackboard()

    async def test_get_and_set(self):
        await self.blackboard.set("key1", "val1", agent_id="agent_a")
        val = await self.blackboard.get("key1")
        self.assertEqual(val, "val1")

        entry = await self.blackboard.get_entry("key1")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.version, 1)
        self.assertEqual(entry.updated_by, "agent_a")

        # Update
        await self.blackboard.set("key1", "val2", agent_id="agent_b")
        entry_v2 = await self.blackboard.get_entry("key1")
        self.assertEqual(entry_v2.version, 2)
        self.assertEqual(entry_v2.updated_by, "agent_b")
        self.assertEqual(await self.blackboard.get("key1"), "val2")

    async def test_ttl_expiration(self):
        await self.blackboard.set("ephemeral", "data", ttl_sec=0.05)
        self.assertEqual(await self.blackboard.get("ephemeral"), "data")
        await asyncio.sleep(0.08)
        self.assertIsNone(await self.blackboard.get("ephemeral"))

    async def test_list_keys_with_prefix(self):
        await self.blackboard.set("agent:1:status", "ok")
        await self.blackboard.set("agent:2:status", "ok")
        await self.blackboard.set("task:1:res", "done")

        keys = await self.blackboard.list_keys("agent:")
        self.assertEqual(keys, ["agent:1:status", "agent:2:status"])

    async def test_checkpoint_save_and_load(self):
        await self.blackboard.set("config:mode", "production")
        await self.blackboard.set("count", 42)

        with tempfile.TemporaryDirectory() as tmp_dir:
            ckpt_path = Path(tmp_dir) / "ckpt.json"
            await self.blackboard.save_checkpoint(ckpt_path)
            self.assertTrue(ckpt_path.exists())

            new_bb = Blackboard()
            await new_bb.load_checkpoint(ckpt_path)
            self.assertEqual(await new_bb.get("config:mode"), "production")
            self.assertEqual(await new_bb.get("count"), 42)


if __name__ == "__main__":
    unittest.main()
