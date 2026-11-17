[English](README.md) · [简体中文](README.zh-CN.md) · **မြန်မာ**

# agent-team

ဤသည်မှာ Claude Code plugin တစ်ခု ဖြစ်သည်။ AI agent များပါဝင်သော အဖွဲ့ဖြစ်ပြီး အခန်းကဏ္ဍတစ်ခုစီသည် ကိုယ်ပိုင် မော်ဒယ်ကို အသုံးပြုသည်။ စီမံကိန်းရေးဆွဲခြင်းမှ pull request တင်ခြင်းအထိ လုပ်ငန်းစဉ်တစ်ခုတည်းကို လိုက်နာသည်။ merge၊ deploy ကဲ့သို့ အရေးကြီးသော အဆင့်များကို ပိုင်ရှင် (owner) ကိုယ်တိုင်သာ လုပ်ဆောင်နိုင်သည်။ terminal အတွက် `team-status` command လည်း ပါဝင်သည်။

![Live view ၏ နမူနာပုံ](docs/media/live-view-preview-cards.png)

*Live view (team-status ၏ `--watch` mode) ၏ နမူနာပုံ ဖြစ်သည်။ ဒေတာများမှာ စိတ်ကူးယဉ်ဖြစ်ပြီး တကယ် run ထားသော screenshot မဟုတ်ပါ။*

ဒီဇိုင်းစာတမ်းမှာ `docs/specs/2026-11-17-agent-team-plugin-design.md` ဖြစ်သည်။

## ထည့်သွင်းခြင်း (စက်တစ်လုံးလျှင် တစ်ကြိမ်)

Claude Code ထဲတွင်:

```
/plugin marketplace add DavidWin105/agent-team
/plugin install agent-team@agent-team-local
```

## Project တစ်ခုတွင် အသုံးပြုခြင်း

1. `/team-init` သည် `.claude/team.json` ကို ဖန်တီးပေးသည်။
2. lead (ဦးဆောင် agent) ကို အလုပ်တစ်ခုအတွက် စီမံကိန်း ရေးခိုင်းပါ။ စီမံကိန်းကို သင်က ခွင့်ပြုပြီးနောက် ထိုစီမံကိန်းအတိုင်း လုပ်ဆောင်ခိုင်းပါ။
3. `/team-status` ကို သုံးပါ။ သို့မဟုတ် ဤ repository ၏ clone ရှိလျှင် မည်သည့် terminal တွင်မဆို `python3 -I agent-team/scripts/team-status <project-dir>` ကို run နိုင်သည်။

### တိုက်ရိုက် ကြည့်ရှုခြင်း

1. Claude Code ထဲတွင် `/team-watch` ကို run ပါ။ plugin folder နှင့် သင့် project folder အစစ်အမှန်တို့ကို ထည့်သွင်းပြီးသား command တစ်ကြောင်းကို ထုတ်ပေးသည်။
2. ဒုတိယ terminal တစ်ခု ဖွင့်ပြီး ထိုစာကြောင်းကို paste လုပ်ပါ။ command သည် အောက်ပါပုံစံ ဖြစ်ပြီး Ctrl+C မနှိပ်မချင်း တစ်စက္ကန့်လျှင် တစ်ကြိမ် refresh လုပ်နေမည်။

```bash
python3 -I <plugin folder>/scripts/team-status --watch <project folder>
```

ဤ repository ၏ clone ရှိလျှင် မည်သည့် terminal တွင်မဆို: `python3 -I agent-team/scripts/team-status --watch <project-dir>`။ terminal အကျယ် ကော်လံ ၁၀၀ နှင့်အထက် ရှိလျှင် card များကို ပြပြီး ပိုကျဉ်းလျှင် ဇယားကို ပြသည်။ `--watch` မပါဘဲ `/team-status` ကိုသာ run လျှင် snapshot တစ်ကြိမ်သာ ထုတ်ပေးသည်။

### Live view က ဘာတွေ ပြသည်၊ ဘာတွေ မပြသည်

team agent တစ်ခုစီ၏ အခန်းကဏ္ဍ၊ တာဝန်ယူထားသော အလုပ်အပိုင်း၊ လက်ရှိအခြေအနေ၊ လုပ်နေသည့်အရာနှင့် tool ခေါ်ဆိုမှု အရေအတွက်ကို ပြသည်။ ဤအချက်အလက်များကို hooks များက မှတ်တမ်းတင်သည်။ မှတ်တမ်းတွင် tool အမည်၊ project နှင့် နှိုင်းယှဉ်သော (သို့မဟုတ် builder ၏ worktree နှင့် နှိုင်းယှဉ်သော) ဖိုင်လမ်းကြောင်းနှင့် Bash command ၏ ပထမစကားလုံးကိုသာ သိမ်းထားသည်။ ဖိုင်အကြောင်းအရာ၊ command ၏ ကျန်အပိုင်း သို့မဟုတ် output ကို လုံးဝ မသိမ်းပါ။ `VAR=value` ဖြင့် စသော command ကို အမည်မပါဘဲ မှတ်တမ်းတင်သည်။ hooks များက agent တစ်ခု မအောင်မြင်ကြောင်း မသိနိုင်သဖြင့် ရပ်သွားသော agent အားလုံးကို ပြီးစီးသည်ဟု ပြသည်။ မအောင်မြင်သော tool ခေါ်ဆိုမှုကို `Bash (failed)` ကဲ့သို့ ပြသည်။ hook field အမည်များသည် စာတမ်းပါအတိုင်း ဖြစ်ပြီး တကယ် run ကြည့်၍ မအတည်ပြုရသေးပါ။

### Live view ကို စစ်ဆေးခြင်း

ရေးသားသူသည် အစစ်အမှန် ပတ်ဝန်းကျင်တွင် မ run ကြည့်ရသေးပါ။ သင်ကိုယ်တိုင် စစ်ဆေးလိုလျှင် အောက်ပါအတိုင်း လုပ်ပါ။

1. စမ်းသပ်ရန် git repository တစ်ခုတွင် plugin ကို ထည့်သွင်းပြီး `/team-init` ကို run ပါ။
2. ဒုတိယ terminal တွင် `python3 -I <path-to>/agent-team/scripts/team-status --watch <scratch-dir>` ကို run ပါ။
3. ပထမ terminal တွင် lead ကို အလုပ်နှစ်ခုပါသော စီမံကိန်းတစ်ခု ရေးပြီး လုပ်ဆောင်ခိုင်းပါ (ဥပမာ ဖိုင်အသီးသီးတွင် `subtract` နှင့် `multiply` function များ)။
4. agent တစ်ခုစီ ပေါ်လာခြင်း၊ လုပ်နေသည့်အရာကို ပြခြင်း၊ နောက်ဆုံးတွင် ပြီးစီးခြင်းအဖြစ် ပြောင်းခြင်းတို့ကို စစ်ဆေးပါ။

## စမ်းသပ်မှုများ

```bash
cd tests && PYTHONPATH=../scripts python3 -m unittest discover -v
```

## လိုင်စင်

MIT။ `LICENSE` ကို ကြည့်ပါ။
