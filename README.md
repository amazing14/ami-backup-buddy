# ami-backup-buddy
Take AMI snapshots periodically via lambda

![Robot](robot-emoji.png "Robot")


## Install
```
./deploy_job.sh --lambda                                                                                              

Usage: deploy_job.sh --all | --iam | --lambda | --schedule

Note:
--all      : deploy ALL components
--iam      : deploy ONLY IAM role and policy for lambda function(s)
--lambda   : deploy ONLY lambda function(s)
--schedule : deploy ONLY scheduled events for lambda function(s)
```

The project is broken down into a few components:
- Lambda code (Python)
- An IAM role + policy that grants the lambda code enough rights to perform its function
- A Cloudwatch schedule, which will `trigger` lambda into running the backups
- A bash script to `push` the code unto AWS's specific silos

Each `--flag` on `deploy.sh` allows for updating each portion separately on AWS:

- `--iam` will deploy the contents of `iam-policy.json` and `iam-trust.json` to the corresponding IAM policy used by the lambda functions. These control enough access to query EC2 snapshots, read logs, and publish a message to an SNS queue.
- `--lambda` will zip and deploy the python code unto lambda.
- `--schedule` will update the `cron`-like scheduled runs for triggering the lambda functions.

Don't forget to update the `tag key` + `tag value` used [here](https://github.com/ifarfan/ami-backup-buddy/blob/master/ami_shared.py#L23-L24) to match your own. These are used by the lambda functions to query which servers will be the ones snapshotted.

Last, how long to keep AMIs for and how often they are taken are set [here](https://github.com/ifarfan/ami-backup-buddy/blob/master/ami_shared.py#L26-L29). Again, update to your own values.


## Notifications
Set to notify via Slack / Email (via SNS) on success and failure.

Update the [following lines](https://github.com/ifarfan/ami-backup-buddy/blob/master/ami_shared.py#L37-L40) with your own values.


## **Pre-requisites:**

* Python 2.7+
* An AWS account + credentials with access to *Lambda*
* Bash 4.x+


## **Oh god, why?!?:**

Because _**serverless**_ is currently all the rage... :sunglasses: :grimacing:


I've been to enough places that have really old, irreplaceble and unrebootable AWS EC2 instances laying around with not enough documentation behind them that, at a minimum, require for some sort of backup plan around them in the event they go **bump** in the middle of the night.

So, for this scenario I wrote this little smidgen of python that, when invoked via scheduled *lambda* functions, does the following:

- Take **no-reboot** snapshots of specific EC2 instances (defined by having an specific Name/Value pair instance "tag" )
- Keep them around for an specified period of time (also defined by another specific Name/Value pair instance "tag")
- Remove snapshots after specified expiration date is reached (also defined by... *you guessed it*, another specific Name/Value pair instance "tag")
- Notify via email / Slack when either of the above actions takes place, and whether it was executed successfully or not

So there you have it, that's all there's to it.

I've been doing this task in all sorts of manners for years but once *lambda* came about it was the final piece of the puzzle: the bulk of the work is done by the snapshot engine anyways, I just needed a way to automatically schedule it without requiring *cron* on a managed VM/instance/container (although technically *lambda* is a container behind the scenes, but since it's not **my** container I don't have to worry about managing it).

So... come to think to it, this whole *serverless* thing does have its merits... ¯\\\_(ツ)\_/¯  ).
