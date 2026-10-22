"use client";
import { createContext, useContext, useState, type ReactNode } from "react";
import { flushSync } from "react-dom";

export type Lang = "fa" | "en";

const fa = {
  brand: "فیت‌پیمان",
  tagline: "به قولت عمل کن، پاداش بگیر",
  nav: { today: "امروز", pacts: "پیمان‌ها", wallet: "کیف پول", community: "جامعه", account: "حساب کاربری" },
  toman: "تومان",
  theme: "تغییر پوسته",
  langSwitch: "English",
  type: { gym: "باشگاه", steps: "قدم‌ها", nutrition: "تغذیه" },
  typeDesc: { gym: "حداقل ۳۰ دقیقه حضور در باشگاه", steps: "رسیدن به هدف قدم روزانه", nutrition: "ثبت ۳ وعده غذایی در روز" },
  unit: { gym: "دقیقه", steps: "قدم", nutrition: "وعده" },
  checkin: { gym: "ثبت حضور", steps: "ثبت قدم‌ها", nutrition: "ثبت وعده" },
  hello: (n: string) => `سلام ${n}`,
  streak: (n: string) => `${n} روز پیاپی`,
  ofDays: (a: string, b: string) => `${a} از ${b} روز`,
  thisWeek: "این هفته",
  today: "امروز",
  done: "انجام شد",
  atRisk: "در خطر",
  pool: "صندوق این هفته",
  poolHint: "مبلغی که اعضا در گرو گذاشته‌اند و هنوز به هدفشان نرسیده‌اند. به پیمانت پایبند بمان تا سهمت را بگیری.",
  view: "مشاهده",
  save: "ثبت",
  cancel: "انصراف",
  gymHint: "جلسه‌های کمتر از ۳۰ دقیقه حساب نمی‌شوند.",
  stepsPlaceholder: "تعداد قدم",
  saved: "ثبت شد",
  noPacts: "هنوز پیمانی نبسته‌ای",
  noPactsHint: "یک پیمان کوچک ببند؛ قدم اول همیشه سخت‌ترین است.",
  myPacts: "پیمان‌های من",
  newPact: "پیمان تازه",
  active: "فعال",
  perMiss: "هر روز جاافتاده",
  perWeek: "روز در هفته",
  dailyGoal: "هدف روزانه",
  q1: "چه پیمانی می‌بندی؟",
  q2: "چند روز در هفته؟",
  q3: "هر روز جاافتاده چقدر برایت هزینه دارد؟",
  summary: "خلاصه پیمان",
  maxRisk: "بیشترین مبلغ در خطر در هفته",
  win: "به هدف برسی، از صندوق سهم می‌گیری",
  hold: "برای بستن پیمان نگه دار",
  sealed: "پیمان بسته شد!",
  next: "ادامه",
  back: "بازگشت",
  err: {
    exists: "این پیمان را از قبل داری", points: "امتیاز کافی نیست", settled: "این هفته بسته شده است", generic: "مشکلی پیش آمد. دوباره امتحان کن.",
    auth: "برای ادامه وارد شو", phone: "شماره تلفن همراه نادرست است", code: "کد تایید نادرست است یا منقضی شده",
    locked: "چند بار کد نادرست نوشتی. ۱۵ دقیقه دیگر دوباره امتحان کن.", rate_limited: "درخواست‌ها زیاد بود. کمی بعد دوباره امتحان کن.",
    limit: "برای امروز به سقف ثبت این پیمان رسیدی", days: "روزهای باقی‌مانده این هفته کمتر از این است", balance: "موجودی کافی نیست",
    value: "مقدار نادرست است", name: "نام نادرست است", too_large: "اطلاعات ارسالی زیاد است", csrf: "درخواست نامعتبر بود. صفحه را دوباره باز کن.",
    invalid: "اطلاعات واردشده نادرست است", topup_unavailable: "افزایش موجودی هنوز فعال نیست",
    sms_unavailable: "ارسال پیامک اکنون ممکن نیست. کمی بعد دوباره امتحان کن.", active_pacts: "ابتدا پیمان‌های فعال را لغو کن و تا پایان هفته صبر کن.", has_balance: "تا وقتی موجودی در کیف پول مانده، حذف حساب کاربری ممکن نیست.",
    not_found: "پیدا نشد", held: "سامانه موقتاً برای بررسی متوقف شده است. کمی بعد دوباره امتحان کن.", network: "اتصال به سرور برقرار نشد. اینترنتت را بررسی کن.", server: "مشکلی در سرور پیش آمد. دوباره امتحان کن.",
  },
  retry: "تلاش دوباره",
  balance: "موجودی",
  points: "امتیاز",
  topup: "افزایش موجودی",
  demo: "نسخه نمایشی",
  txns: "تراکنش‌ها",
  txn: { topup: "افزایش موجودی", reward: "پاداش پیمان", penalty: "جریمه روز جاافتاده", paused: "پیمان‌ها متوقف شدند: موجودی کافی نبود" } as Record<string, string>,
  rewards: "فروشگاه پاداش",
  reward: { gym20: "۲۰٪ تخفیف باشگاه", coach: "یک جلسه مشاوره تغذیه", bottle: "بطری آب ورزشی", charity: "کمک به خیریه سلامت" } as Record<string, string>,
  soon: "به‌زودی",
  noMoney: "بدون پول",
  noMoneyNote: "بدون مبلغ تعهد؛ فقط امتیاز و رکورد پیاپی.",
  atStake: "در گرو این هفته",
  members: "عضو",
  onTrack: "پیمان در مسیر",
  split: "تقسیم صندوق",
  winners: "برندگان",
  fee: "کارمزد خدمت",
  charity: "خیریه سلامت",
  charityNote: "سهم هر برنده حداکثر ۳ برابر تعهد خودش است. باقی‌مانده، و سهم برندگان وقتی برنده‌ای نیست، به خیریه سلامت می‌رسد.",
  board: "جدول این هفته",
  you: "شما",
  settle: "بستن هفته",
  result: "نتیجه هفته",
  yourShare: "سهم شما",
  close: "بستن",
  bizTitle: "سلامت کارکنان، قابل اندازه‌گیری",
  bizSub: "برای تیمتان کارزار سلامت راه بیندازید، مشارکت را ببینید و به باشگاه‌های شریک، مشتری وفادار بدهید.",
  bizCta: "مشاهده قیمت‌ها",
  activeMembers: "عضو فعال",
  activePacts: "پیمان فعال",
  completion: "نرخ انجام این هفته",
  byType: "انجام به تفکیک پیمان",
  activity: "ثبت‌ها در ۱۴ روز گذشته",
  pricing: "قیمت‌ها",
  perMonth: "در ماه",
  popular: "محبوب",
  plans: [
    { name: "رایگان", price: "۰", f: ["تا سه پیمان فعال", "جدول جامعه", "سهم از صندوق"] },
    { name: "پریمیوم", price: "۱۴۹ هزار", f: ["پیمان‌های نامحدود", "گزارش کالری و درشت‌مغذی‌ها", "پیشنهاد غذای ایرانی", "کارمزد کمتر"] },
    { name: "سازمانی", price: "۹۰ تا ۱۸۰ هزار", f: ["پیش‌خوان سازمانی", "کارزار سلامت کارکنان", "گزارش مشارکت تجمیعی", "کوپن باشگاه‌های شریک"], per: "به ازای هر کارمند" },
  ],
  feeNote: (p: string) => `کارمزد خدمت ${p} از صندوق برداشته می‌شود؛ بقیه به برندگان یا خیریه سلامت می‌رسد.`,
  login: {
    title: "ورود یا ثبت‌نام", sub: "شماره تلفن همراهت را بنویس تا کد تایید برایت پیامک شود.", phone: "شماره تلفن همراه", send: "دریافت کد تایید",
    codeTitle: "کد تایید را بنویس", codeSub: (p: string) => `کد ۶ رقمی به ${p} پیامک شد.`, code: "کد تایید", verify: "ورود",
    resend: "ارسال دوباره کد", resendIn: (s: string) => `ارسال دوباره تا ${s} ثانیه دیگر`, edit: "تغییر شماره", demoCode: "کد نسخه نمایشی",
  },
  account: {
    sub: "اطلاعات و تنظیمات", name: "نام نمایشی", nameHint: "این نام در جدول جامعه دیده می‌شود.", phone: "شماره تلفن همراه", language: "زبان", theme: "پوسته",
    logout: "خروج از حساب کاربری", logoutAll: "خروج از همه دستگاه‌ها", del: "حذف حساب کاربری", delTitle: "حساب کاربری حذف شود؟",
    delBody: "شماره تلفن و نام تو پاک می‌شود. این کار برگشت‌پذیر نیست.", delConfirm: "حذف", forTeams: "برای سازمان‌ها", forTeamsHint: "کارزار سلامت کارکنان و گزارش مشارکت", saved: "ذخیره شد",
  },
  endPact: "لغو پیمان", endTitle: "پیمان لغو شود؟", endBody: "پیمان تا پایان همین هفته فعال می‌ماند و جریمه روزهای جاافتاده این هفته حساب می‌شود.",
  endsAt: (d: string) => `پایان: ${d}`, available: "موجودی قابل استفاده", notEnough: "موجودی برای این مبلغ کافی نیست",
  confirm: "تایید", settleTitle: "این هفته همین حالا بسته شود؟", settleBody: "روزهای باقی‌مانده جاافتاده حساب می‌شوند. این کار برگشت‌پذیر نیست.",
  holdAlt: "با صفحه‌کلید یا فناوری کمکی، همین دکمه را فعال کن.", loading: "در حال بارگیری", skip: "رفتن به محتوا",
  pausedMsg: "پیمان‌هایت متوقف شدند، چون موجودی برای هفته بعد کافی نبود. موجودی‌ات را افزایش بده و پیمان تازه ببند.",
  renews: "هر هفته به‌صورت خودکار تمدید می‌شود تا لغوش کنی",
  priceNote: "قیمت‌ها نمایشی‌اند و هنوز فعال نیستند.", rewardsNote: "تحویل پاداش‌ها به‌زودی فعال می‌شود؛ دریافت‌هایت ثبت می‌شوند.",
};

type Dict = typeof fa;

const en: Dict = {
  brand: "FitPeyman",
  tagline: "Keep your word. Get paid.",
  nav: { today: "Today", pacts: "Pacts", wallet: "Wallet", community: "Community", account: "Account" },
  toman: "Toman",
  theme: "Toggle theme",
  langSwitch: "فارسی",
  type: { gym: "Gym", steps: "Steps", nutrition: "Nutrition" },
  typeDesc: { gym: "At least 30 minutes at the gym", steps: "Hit your daily step goal", nutrition: "Log 3 meals a day" },
  unit: { gym: "min", steps: "steps", nutrition: "meals" },
  checkin: { gym: "Check in", steps: "Add steps", nutrition: "Log meal" },
  hello: (n) => `Hi, ${n}`,
  streak: (n) => `${n}-day streak`,
  ofDays: (a, b) => `${a} of ${b} days`,
  thisWeek: "This week",
  today: "Today",
  done: "Done",
  atRisk: "At risk",
  pool: "This week's pool",
  poolHint: "Money on the line from members who haven't hit their goal yet. Keep your pact to take your share.",
  view: "View",
  save: "Save",
  cancel: "Cancel",
  gymHint: "Sessions under 30 minutes don't count.",
  stepsPlaceholder: "Step count",
  saved: "Saved",
  noPacts: "No pacts yet",
  noPactsHint: "Start with a small one. The first step is always the hardest.",
  myPacts: "My pacts",
  newPact: "New pact",
  active: "Active",
  perMiss: "Per missed day",
  perWeek: "days a week",
  dailyGoal: "Daily goal",
  q1: "What will you commit to?",
  q2: "How many days a week?",
  q3: "What will a missed day cost you?",
  summary: "Your pact",
  maxRisk: "Most you can lose in a week",
  win: "Hit it and you share the pool",
  hold: "Hold to seal the pact",
  sealed: "Pact sealed!",
  next: "Continue",
  back: "Back",
  err: {
    exists: "You already have this pact", points: "Not enough points", settled: "This week is already closed", generic: "Something went wrong. Try again.",
    auth: "Sign in to continue", phone: "That phone number isn't valid", code: "That code is incorrect or has expired",
    locked: "Too many incorrect codes. Try again in 15 minutes.", rate_limited: "Too many requests. Try again in a moment.",
    limit: "You've reached today's limit for this pact", days: "Fewer days are left this week than that", balance: "Not enough balance",
    value: "That value isn't valid", name: "That name isn't valid", too_large: "That request is too large", csrf: "Request rejected. Reload the page.",
    invalid: "Some details aren't valid", topup_unavailable: "Adding funds isn't available yet",
    sms_unavailable: "Can't send text messages right now. Try again shortly.", active_pacts: "End your active pacts first and wait for the week to close.", has_balance: "You can't delete your account while money remains in your wallet.",
    not_found: "Not found", held: "Paused for a safety check. Try again shortly.", network: "Can't reach the server. Check your connection.", server: "Server problem. Try again.",
  },
  retry: "Try again",
  balance: "Balance",
  points: "Points",
  topup: "Add funds",
  demo: "Demo",
  txns: "Transactions",
  txn: { topup: "Top-up", reward: "Pact reward", penalty: "Missed-day penalty", paused: "Pacts paused: balance too low" },
  rewards: "Rewards",
  reward: { gym20: "20% off a gym pass", coach: "Nutrition coaching session", bottle: "Sports water bottle", charity: "Donate to a health charity" },
  soon: "Soon",
  noMoney: "No money",
  noMoneyNote: "No stake; points and a streak only.",
  atStake: "On the line this week",
  members: "members",
  onTrack: "pacts on track",
  split: "How the pool splits",
  winners: "Winners",
  fee: "Service fee",
  charity: "Health charity",
  charityNote: "Each winner takes at most 3x their own commitment. The remainder, and the winners' share when nobody wins, goes to a health charity.",
  board: "This week's board",
  you: "You",
  settle: "Close the week",
  result: "Week result",
  yourShare: "Your share",
  close: "Close",
  bizTitle: "Employee wellness you can measure",
  bizSub: "Run wellness campaigns for your team, see real participation, and send loyal members to partner gyms.",
  bizCta: "See pricing",
  activeMembers: "Active members",
  activePacts: "Active pacts",
  completion: "Completion this week",
  byType: "Completion by pact",
  activity: "Check-ins, last 14 days",
  pricing: "Pricing",
  perMonth: "/ month",
  popular: "Popular",
  plans: [
    { name: "Free", price: "0", f: ["Up to 3 active pacts", "Community board", "Share of the pool"] },
    { name: "Premium", price: "149k", f: ["Unlimited pacts", "Calorie & macro reports", "Iranian meal ideas", "Lower fee"] },
    { name: "Business", price: "90–180k", f: ["Company dashboard", "Employee wellness campaigns", "Aggregate participation reports", "Partner gym coupons"], per: "per employee" },
  ],
  feeNote: (p) => `A ${p} service fee comes out of the pool; the rest goes to winners or a health charity.`,
  login: {
    title: "Sign in or sign up", sub: "Enter your mobile number and we'll text you a verification code.", phone: "Mobile number", send: "Get verification code",
    codeTitle: "Enter the code", codeSub: (p: string) => `We texted a 6-digit code to ${p}.`, code: "Verification code", verify: "Sign in",
    resend: "Resend code", resendIn: (s: string) => `Resend in ${s}s`, edit: "Change number", demoCode: "Demo code",
  },
  account: {
    sub: "Profile and settings", name: "Display name", nameHint: "Shown on the community board.", phone: "Mobile number", language: "Language", theme: "Theme",
    logout: "Sign out", logoutAll: "Sign out of all devices", del: "Delete account", delTitle: "Delete your account?",
    delBody: "Your phone number and name are erased. This can't be undone.", delConfirm: "Delete", forTeams: "For teams", forTeamsHint: "Employee wellness campaigns and participation reports", saved: "Saved",
  },
  endPact: "End pact", endTitle: "End this pact?", endBody: "It stays active until this week closes, and this week's missed days still count.",
  endsAt: (d: string) => `Ends ${d}`, available: "Available balance", notEnough: "Not enough balance for this amount",
  confirm: "Confirm", settleTitle: "Close this week right now?", settleBody: "Remaining days count as missed. This can't be undone.",
  holdAlt: "With a keyboard or assistive tech, just activate this button.", loading: "Loading", skip: "Skip to content",
  pausedMsg: "Your pacts were paused because your balance can't cover next week. Add funds, then seal a new pact.",
  renews: "Renews automatically every week until you end it",
  priceNote: "Prices are illustrative; plans aren't live yet.", rewardsNote: "Reward delivery is coming soon; your redemptions are recorded.",
};

type Ctx = {
  lang: Lang;
  t: Dict;
  setLang: (l: Lang) => void;
  n: (x: number) => string;
  money: (x: number) => string;
  pct: (x: number) => string;
  date: (iso: string, o: Intl.DateTimeFormatOptions) => string;
};
const LangCtx = createContext<Ctx>(null!);

export function LangProvider({ initial, children }: { initial: Lang; children: ReactNode }) {
  const [lang, set] = useState(initial);
  const loc = lang === "fa" ? "fa-IR" : "en-US";
  const n = (x: number) => x.toLocaleString(loc);
  const setLang = (l: Lang) => {
    document.cookie = `lang=${l};path=/;max-age=31536000;samesite=lax${location.protocol === "https:" ? ";secure" : ""}`;
    const apply = () => {
      flushSync(() => set(l));
      document.documentElement.lang = l;
      document.documentElement.dir = l === "fa" ? "rtl" : "ltr";
    };
    if (document.startViewTransition) document.startViewTransition(apply);
    else apply();
  };
  const value: Ctx = {
    lang, setLang, n, t: lang === "fa" ? fa : en,
    pct: (x) => (x / 100).toLocaleString(loc, { style: "percent" }),
    money: (x) => `${n(x)} ${lang === "fa" ? fa.toman : en.toman}`,
    date: (iso, o) => new Date(iso + "T12:00:00").toLocaleDateString(lang === "fa" ? "fa-IR-u-ca-persian" : "en-US", o),
  };
  return <LangCtx.Provider value={value}>{children}</LangCtx.Provider>;
}

export const useT = () => useContext(LangCtx);

/** Localised text for a backend error code; unknown codes fall back to the generic message. */
export const errText = (t: Dict, e: unknown) => {
  const code = e instanceof Error ? e.message : "";
  return (t.err as Record<string, string>)[code] ?? t.err.generic;
};
