# ami-backup-buddy
Take AMI snapshots periodically via lambda

![Robot](robot-emoji.png "Robot")

I've been to enough places that have really old, irreplaceble and unrebootable AWS EC2 instances laying around with not enough documentation behind them that, at a minimum, require for some sort of backup plan around them in the event they go **bump** in the middle of the night.

So, for this scenario I wrote this little smidgen of python that, when invoked via scheduled *lambda* functions, does the following:

- Take **no-reboot** snapshots of specific EC2 instances (defined by having an specific Name/Value pair instance "tag" )
- Keep them around for an specified period of time (also defined by another specific Name/Value pair instance "tag")
- Remove snapshots after specified expiration date is reached (also defined by... *you guessed it*, another specific Name/Value pair instance "tag")
- Notify via email / Slack when either of the above actions takes place, and whether it was executed successfully or not

So there you have it, that's all there's to it.

I've been doing this task in all sorts of manners for years but once *lambda* came about it was the final piece of the puzzle: the bulk of the work is done by the snapshot engine anyways, I just needed a way to automatically schedule it without requiring *cron* on a managed VM/instance/container (although technically *lambda* is a container behind the scenes, but since it's not **my** container I don't have to worry about it... ¯\\\_(ツ)\_/¯  ).
