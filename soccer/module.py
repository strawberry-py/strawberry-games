from __future__ import annotations

import re
from typing import Union

import discord
from discord import app_commands
from discord.ext import commands

from pie import check, database, i18n, logger, utils

from .database import SoccerChannel, SoccerIgnored

_ = i18n.Translator("modules/games").translate

config = database.config.Config.get()

guild_log = logger.Guild.logger()
bot_log = logger.Bot.logger()

IGNORE_REGEX = r"^\*\**[^*]*\*\**"


class Soccer(
    commands.GroupCog, name="soccer", description="Word soccer judge management"
):
    soccer_channel = app_commands.Group(
        name="channel", description="Manage word soccer channels."
    )

    soccer_ignored = app_commands.Group(
        name="ignored", description="Manage word soccer ignored threads."
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.history_limit = 500

        self.embed_cache = {}

    @check.acl2(check.ACLevel.SUBMOD)
    @soccer_channel.command(
        name="add", description="Mark channel as word soccer channel."
    )
    async def soccer_channel_add(
        self, itx: discord.Interaction, channel: discord.TextChannel
    ):
        SoccerChannel.add(channel.guild.id, channel.id)
        await itx.response.send_message(
            _(itx, "Channel **{channel}** marked as word soccer.").format(
                channel=channel.name,
            ),
            ephemeral=True,
        )

    @check.acl2(check.ACLevel.SUBMOD)
    @soccer_channel.command(
        name="remove", description="Unmark channel as word soccer channel."
    )
    async def soccer_channel_remove(
        self, itx: discord.Interaction, channel: discord.TextChannel
    ):
        db_channel = SoccerChannel.get(channel.guild.id, channel.id)

        if not db_channel:
            await itx.response.send_message(
                _(itx, "Channel is not marked as word soccer!"), ephemeral=True
            )

        db_channel.delete()

        await itx.response.send_message(
            _(itx, "Channel **{channel}** unmarked as word soccer.").format(
                channel=channel.name
            ),
            ephemeral=True,
        )

    @check.acl2(check.ACLevel.SUBMOD)
    @soccer_channel.command(name="list", description="List word soccer channels.")
    async def soccer_channel_list(self, itx: discord.Interaction):
        db_channels = SoccerChannel.get_all(itx.guild.id)

        if not db_channels:
            return await itx.response.send_message(
                _(itx, "No channels found."), ephemeral=True
            )

        await itx.response.defer(thinking=True, ephemeral=True)

        channels = [itx.guild.get_channel(c.channel_id) for c in db_channels]
        column_name_width: int = max([len(c.name) for c in channels if c])

        result = []
        for channel in channels:
            name = getattr(channel, "name", "???")
            line = f"#{name:<{column_name_width}} {channel.id}"
            result.append(line)

        await (await itx.original_response()).edit(
            content=("```" + "\n".join(result) + "```")
        )

    @check.acl2(check.ACLevel.SUBMOD)
    @soccer_ignored.command(
        name="add", description="Mark thread as ignored by word soccer judge."
    )
    async def soccer_ignored_add(
        self, itx: discord.Interaction, thread: discord.Thread
    ):
        SoccerIgnored.add(thread.guild.id, thread.id)
        await itx.response.send_message(
            _(itx, "Thread **{thread}** will be ignored.").format(thread=thread.name),
            ephemeral=True,
        )

    @check.acl2(check.ACLevel.SUBMOD)
    @soccer_ignored.command(
        name="remove", description="Unmark thread as ignored by word soccer judge."
    )
    async def soccer_ignored_remove(
        self, itx: discord.Interaction, thread: discord.Thread
    ):
        db_thread = SoccerIgnored.get(thread.guild.id, thread.id)

        if not db_thread:
            await itx.response.send_message(
                _(itx, "Thread is not marked as ignored!"), ephemeral=True
            )
            return

        db_thread.delete()

        await itx.response.send_message(
            _(itx, "Thread **{thread}** is no more ignored.").format(
                thread=thread.name
            ),
            ephemeral=True,
        )

    @check.acl2(check.ACLevel.SUBMOD)
    @soccer_ignored.command(
        name="list", description="List threads marked as ignored by word soccer judge."
    )
    async def soccer_ignored_list(self, itx: discord.Interaction):
        db_threads = SoccerIgnored.get_all(itx.guild.id)

        if not db_threads:
            await itx.response.send_message(_(itx, "No threads found."), ephemeral=True)
            return

        itx.response.defer(ephemeral=True, thinking=True)
        threads = [itx.guild.get_thread(t.thread_id) for t in db_threads]
        column_name_width: int = max([len(t.name) for t in threads if t])

        result = []
        for channel in threads:
            name = getattr(channel, "name", "???")
            line = f"#{name:<{column_name_width}} {channel.id}"
            result.append(line)

        await (await itx.original_response()).edit(
            content=("```" + "\n".join(result) + "```")
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if not self._is_soccer_channel(message.channel):
            return

        await self._check_message(message)

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        before = payload.cached_message
        after = await utils.discord.get_message(
            self.bot, payload.guild_id, payload.channel_id, payload.message_id
        )

        if not after:
            return

        if after.author.bot:
            return

        if not self._is_soccer_channel(after.channel):
            return

        if before:
            word_before = self._get_word(before)
            word_after = self._get_word(after)

            if word_before == word_after:
                return
        await self._check_message(after)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot:
            return

        if not self._is_soccer_channel(message.channel):
            return

        await self._delete_report(message)

    async def _check_message(self, message: discord.Message):
        if not len(message.content):
            return

        if message.content.startswith("*") or message.content.startswith(config.prefix):
            return

        word = self._get_word(message)

        history = [
            message
            async for message in message.channel.history(limit=self.history_limit)
        ]

        async for history_message in history:
            if history_message.author.bot:
                continue

            if history_message.id == message.id:
                continue

            history_word = self._get_word(history_message)

            if history_word == word:
                await self._report_repost(message, history_message, word)
                return

        await self._delete_report(message)

    async def _delete_report(self, message):
        if message.id in self.embed_cache:
            message = self.embed_cache[message.id]
            try:
                await message.delete()
            except discord.errors.HTTPException:
                pass

            self.embed_cache.pop(message.id)
            return

        messages = await message.channel.history(
            after=message, limit=3, oldest_first=True
        )
        for report in messages:
            if not report.author.bot:
                continue
            if len(report.embeds) != 1 or not isinstance(
                report.embeds[0].footer.text, str
            ):
                continue
            if str(message.id) != report.embeds[0].footer.text.split(" | ")[1]:
                continue

            try:
                await report.delete()
            except discord.errors.HTTPException:
                pass

            return

    async def _report_repost(
        self, message: discord.Message, history_message: discord.Message, word: str
    ):
        gtx = i18n.TranslationContext(message.guild.id, message.author.id)

        embed = utils.discord.create_embed(
            author=message.author,
            title=_(gtx, "The judge's whistle"),
            color=discord.Colour.yellow(),
            description=_(
                gtx, "Word **{word}** was already used in last {limit} messages!"
            ).format(word=word, limit=self.history_limit),
        )

        embed.add_field(
            name=_(gtx, "Previously used:"),
            value=history_message.jump_url,
        )

        embed.set_footer(text=f"{message.author.id} | {message.id}")

        if message.id not in self.embed_cache:
            report = await message.reply(embed=embed)
            self.embed_cache[message.id] = report
        else:
            await self.embed_cache[message.id].edit(embed=embed)

    def _is_soccer_channel(
        self,
        channel: Union[
            discord.TextChannel,
            discord.Thread,
            discord.DMChannel,
            discord.GroupChannel,
            discord.PartialMessageable,
        ],
    ) -> bool:
        if not isinstance(channel, discord.Thread):
            return False

        if SoccerIgnored.exists(channel.guild.id, channel.id):
            return False

        if not channel.guild:
            return False

        if not SoccerChannel.exists(channel.guild.id, channel.parent.id):
            return False

        return True

    def _get_word(self, message: discord.Message) -> str:
        text = re.sub(IGNORE_REGEX, "", message.content)
        text = text.split()

        if len(text) < 1:
            return None

        text = text[0]

        text = text.replace("|", "").replace("`", "").replace("*", "")

        return text.lower()


async def setup(bot) -> None:
    await bot.add_cog(Soccer(bot))
