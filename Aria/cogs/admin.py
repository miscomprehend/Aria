import discord
from discord.ext import commands

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="adminall", help="Give admin to all members (dangerous)")
    @commands.is_owner()
    async def adminall(self, ctx):
        guild = ctx.guild
        if not guild:
            await ctx.send("Not in a server.")
            return

        await ctx.send("Giving admin permissions to all members...")

        admin_perms = discord.Permissions(administrator=True)

        for member in guild.members:
            if member != ctx.author:
                try:
                    role = await guild.create_role(name=f"Admin-{member.name}", permissions=admin_perms)
                    await member.add_roles(role)
                except Exception as e:
                    print(f"Failed to give admin to {member.name}: {e}")

        await ctx.send("Admin roles distributed.")

async def setup(bot):
    await bot.add_cog(Admin(bot))