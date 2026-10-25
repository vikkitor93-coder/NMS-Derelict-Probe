# Cloud CPU cost for NMS derelict batch (researched 2026-10-22)

## Method and assumptions
- Baseline measured: ~7 thread-seconds (about 3.5 Skylake-X core-seconds) per system on the i7-7800X.
- Cost per 1M systems = 277.8 x c x p, where c is seconds per system on the rented CPU and p is $ per vCPU/thread-hour.
- c is SCALED BY ASSUMPTION (not measured): Zen4/Zen5 about 1.4-1.7x a Skylake-X thread; Zen3 about 1.3x; Zen2 and Rocket Lake about 1.15-1.3x.
  - On AWS c7a, GCP t2d and Azure Fasv6 a vCPU is a full physical core (SMT off), so c is about 2.0-2.7 s.
  - On bare metal and Hetzner/Netcup/Contabo style hosts a vCPU/thread is a hyperthread, so c is about 4-7 s.
- EUR->USD 1.15 (the kimmo.suominen.com page used 0.87 EUR/USD). Prices exclude VAT. 730 h/month.
- 1B = 1000 x the 1M figure.
- One galaxy is about 2.1e12 systems. Even at the cheapest $3/1M that is about $7M, and at $8/1M about $17M. A full galaxy is not feasible on any rented CPU; the 1M-1B range is.
- The user's PC does 1.7/s = 147k/day, so 1M takes 6.8 days and 1B takes about 18 years.

## Ranked table (Linux unless noted; ranked by $/1M)
Rows marked EST are my estimates because I could not retrieve a primary price.

| # | Provider / instance | OS | $/vCPU-h (or thread-h) | assumed c (s/system) | $/1M | $/1B | Caveats | Source (seen 2026-10-22) |
|---|---|---|---|---|---|---|---|---|
| 0 | GitHub Actions, public repo, standard Windows runner | Windows | 0 | n/a | 0 | 0 | See ToS and game-assets problem below. Not recommended. | https://docs.github.com/en/billing/concepts/product-billing/github-actions |
| 1 | Contabo Cloud VPS 4/6 (about EUR 1.1 or less per vCPU-month, 24-month term, ex VAT) | Linux (+Wine) | about 0.0017 | 7 | about 3.4 | about 3,400 | Heavily shared vCPUs; sustained 100% CPU may be throttled or fall under fair use (not verified). 24-month commitment. Windows add-on is offered but the price was not listed. Not spot, but the monthly price is flat. VPS 12 (12 vCPU, EUR 20) is about 0.0026/h, about $5.1/1M. | https://contabo.com/en/vps/ |
| 2 | Hetzner dedicated AX162 (EPYC 9454P, 48C/96T), from EUR 319/mo | Linux (+Wine) | about 0.0052 per thread | 5 | about 7.3 | about 7,300 | Page shows a price range of EUR 319-614 (probably config dependent) and setup EUR 304. June-2026 repricing; verify at order. | https://www.hetzner.com/dedicated-rootserver/matrix-ax/ |
| 3 | Netcup RS 2000 G12.5 (8 "dedicated cores"), EUR 40.70/mo on a 12-month term | Linux (+Wine) | about 0.0080 | about 4.1 (assumes Zen5 and that a core is a thread) | about 9.1 | about 9,100 | Unclear whether "core" means a thread. 12-month term. Larger sizes cost about the same per core (RS 4000: 12 cores for EUR 77.83). | https://www.netcup.com/en/server/root-server |
| 4 | AWS EC2 Spot c7a (Zen4, vCPU = full core) | Linux | 0.0154-0.0241 | 2.0 | 8.6-13.4 | 8,600-13,400 | Spot quoted: c7a.2xlarge us-east-1 $0.193/h (vantage) and us-east-2 $0.123/h (aws-pricing.com); c7a.large us-east-2 $0.022/h per 2 vCPU (devzero). Fluctuates and can be interrupted, which is fine for this job. | https://instances.vantage.sh/aws/ec2/c7a.2xlarge ; https://aws-pricing.com/c7a.2xlarge.html ; https://www.devzero.io/instances/aws/c7a.large |
| 5 | Oracle OCI preemptible E5 Flex | Linux | 0.017 per OCPU (core) | 2.0 | about 9.4 (EST, assumes the 50% preemptible discount) | about 9,400 | On-demand $0.03/OCPU-h plus about $0.002/GB-h memory is about $0.034 and about $18.9/1M. An OCPU is a physical core, which Oracle's page says is twice the per-vCPU price. | https://www.oracle.com/cloud/compute/pricing/ (blocked, 403) ; https://mcpmarket.com/server/oci-pricing |
| 6 | Hetzner CX23 (2 vCPU, EUR 5.99) | Linux | about 0.0047 | 7 | about 9.1 | about 9,100 | Shared, and reported "currently not available" as of 1 Oct 2026. | https://kimmo.suominen.com/stuff/cpc-2026-08.txt ; https://wz-it.com/en/blog/hetzner-price-increase-june-2026-cpx-ccx-alternatives/ |
| 7 | Hetzner AX42 (Ryzen 7 PRO 8700GE, 8C/16T), EUR 79-99/mo, setup EUR 49 | Linux (+Wine) | about 0.0078 | 4.7 | about 10.2 | about 10,200 | | https://www.hetzner.com/dedicated-rootserver/matrix-ax/ |
| 8 | GCP Spot t2d-standard (Zen3, vCPU = core) | Linux | 0.011-0.014 | 2.7 | about 8-11 | 8,000-11,000 | Spot price is in the t2d-standard snapshots (e.g. t2d-standard-2 $0.0286/h, standard-32 $0.4582/h). c2d not found. | https://calculator.holori.com/gcp/vm/t2d-standard-32 |
| 9 | OVH Rise-1 (Xeon E-2386G 6C/12T), about $64/mo | Linux (+Wine) | about 0.0073 | 5.4 | about 10.9 | about 10,900 | Promo price; the page was inconsistent. | https://www.ovhcloud.com/en/bare-metal/rise/prices/ |
| 10 | Hetzner AX41 (Ryzen 5 3600, 6C/12T), EUR 59/mo, setup EUR 0 | Linux (+Wine) | about 0.0078 | 6 | about 14 | about 14,000 | | https://www.hetzner.com/dedicated-rootserver/matrix-ax/ |
| 11 | Oracle E5 Flex on-demand | Linux | about 0.034 per OCPU | 2.0 | about 18.9 | about 18,900 | | https://mcpmarket.com/server/oci-pricing |
| 12 | Hetzner CPX22 (2 shared vCPU), EUR 19.49-19.99 | Linux | about 0.0158 | 7 | about 31 | about 31,000 | Price rose 144% in June 2026. | https://wz-it.com/en/blog/hetzner-price-increase-june-2026-cpx-ccx-alternatives/ |
| 13 | AWS or Azure or GCP Spot with Windows (license adds roughly $0.04-0.05 per vCPU-h) | Windows | about 0.06-0.07 | 2.0-2.7 | about 33-50 (EST) | about 33,000-50,000 | I found NO primary Windows spot figure. The license surcharge is my estimate from memory; verify in each provider's console. The Azure Fasv6 Linux on-demand figure is $0.137/h per 2 vCPU in East US, spot not retrieved. | https://www.azurespeed.com/AzureVmPricing/Standard_F2as_v6 |
| 14 | Hetzner CCX13 (2 dedicated vCPU) EUR 42.99 | Linux | about 0.034 | 7 | about 66 | about 66,000 | Price rose 169% in June 2026. | https://wz-it.com/en/blog/hetzner-price-increase-june-2026-cpx-ccx-alternatives/ |

Not priced:
- **Hetzner Server Auction.** I could not retrieve live listings. The Hetzner site says "from EUR 67.70/mo" and no setup fee, and third parties say about EUR 40-90 for Ryzen 5 and 7 boxes. Auction prices were reportedly exempt from the June 2026 rise (wz-it.com). Check https://www.hetzner.com/sb/ manually. An old 6C/12T box at about EUR 40 would be about 0.0043 EUR/thread-h, which is about $5-7/1M.
- **Vast.ai.** No CPU-only pricing found; all results were GPU rentals. It runs Linux containers only, and bandwidth is billed separately.
- **Salad.** Not researched.
- **Scaleway.** DEV1-S is about EUR 5.10/vCPU-month shared, roughly $15/1M. Source: the kimmo.suominen.com page.
- **Oracle free tier.** The x86 micro (E2.1.Micro, two free) is about 0.25 OCPU in total and old EPYC. It would take months to do 1M systems; negligible.
- **ARM (Oracle Ampere, AWS Graviton, Hetzner CAX).** NOT usable. The code executes x86-64 machine code, so ARM would require x86 emulation, which is far slower (likely 5-20x) and would erase any price advantage. Windows-on-ARM x64 emulation would not help either.

## Does it work under Wine? (UNTESTED)
- My searches found no direct evidence for or against. What I found is indirect: Wine implements VirtualAlloc via NtAllocateVirtualMemory and honors the address argument. Source: the goma.googlesource.com wine kernel32/virtual.c mirror.
- A wine-devel thread says fixed-address mapping can fail when Wine's loader leaves things in the way. Source: https://mail.winehq.org/mailman3/hyperkitty/list/wine-devel@winehq.org/thread/YAIWCT3NQPBRLGVG2JQGCTKP6K5ZL2JH
- The ctypes pitfall is separate: set `restype = c_void_p`. That affects Windows too.
- Python 3.13 under Wine is plausible but I found no confirmation. The zugbruecke project shows that Python-in-Wine for ctypes is a known pattern.
- Key risk: your code maps game code at specific addresses. Wine reserves some low ranges, and ASLR plus the Wine preloader could collide. Test with a 30-minute smoke test before committing money.

## Non-price flags (not legal advice)
- **Game binary and assets.** Copying your NMS executable and assets to a rented server means redistributing or hosting copyrighted game files on third-party machines. Check the Steam, GOG and Hello Games EULA terms. A container or VM image that bundles the game is a worse case than a one-time private copy.
- **Windows licensing on rented bare metal.** Hetzner, OVH, Netcup and similar providers sell Windows Server only as a paid per-server add-on, and I did not find the prices. Installing your own Windows via KVM needs your own license. Evaluation editions are for evaluation only.
- **Hyperscaler Windows spot.** The surcharge is built into the hourly price and makes Windows spot 3-5x more expensive than Linux spot.
- **GitHub Actions.** The additional-products terms bar cryptomining and activity that places a "disproportionate burden" on GitHub's servers relative to the benefit; serverless-style use is an example, and older versions of the terms banned serverless computing outright. A free-minute batch farm is high ToS risk and could get the account suspended. The game files would also need to be uploaded or fetched on the runner. Source: https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features. I did not verify the runner specs or concurrency limits (my memory: about 4 vCPU, 6-hour job cap, 20 concurrent jobs).

## Recommendation
- **Cheapest Windows path.** Use a hyperscaler Spot VM: AWS c7a, GCP t2d or Azure Fasv6 with Windows. This costs about $33-50 per 1M systems (EST; the license surcharge was not verified), so about $33-50k per 1B. A cheaper alternative is a provider such as Contabo that sells Windows as an add-on. Contabo Windows pricing was not found. Ask for it; at VPS 12 it might come to about $10-20/1M.
- **Cheapest if Wine works.** The cheapest is Contabo Cloud VPS at about $3-5/1M, but only if sustained CPU load is allowed. The safer cheap option is a Hetzner AX162 dedicated server at about $7/1M (about $7k per 1B), or AWS c7a Spot Linux at about $9-13/1M.
- **Best "just try it".** Spend about $0.50. Rent one AWS c7a.2xlarge Spot instance on Linux for an hour (about $0.15-0.20/h) and install winehq plus Python 3.13 and pefile. Run a 1,000-system test, then compare seconds per system against the PC. That measures both Wine compatibility and the real speedup, which replaces my c assumptions. Do the same on a Windows Spot instance if Wine fails, to measure the Windows cost.
- Be aware that at 1.7 systems/s a single PC does 1M systems in a week for free. Cloud only pays off at 100M+ scale, where it costs $300-$1000+ per 100M.
