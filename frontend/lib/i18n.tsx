"use client";
import { createContext, useContext, useState, type ReactNode } from "react";
import { flushSync } from "react-dom";

export type Lang = "fa" | "en";

const fa = {
  brand: "فیت‌پیمان",
  tagline: "به قولت عمل کن، پاداش بگیر",
  nav: { today: "امروز", pacts: "پیمان‌ها", wallet: "کیف پول", community: "جامعه", business: "سازمان‌ها" },
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
  kcal: "کالری",
  foods: ["قورمه‌سبزی", "کباب کوبیده", "عدسی", "سالاد شیرازی", "آش رشته", "املت", "جوجه‌کباب", "نان و پنیر و گردو"],
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
  hold: "برای بستن پیمان نگه دارید",
  sealed: "پیمان بسته شد!",
  next: "ادامه",
  back: "بازگشت",
  err: { exists: "این پیمان را از قبل داری", points: "امتیاز کافی نیست", settled: "این هفته قبلا بسته شده است", generic: "مشکلی پیش آمد. دوباره امتحان کنید." },
  retry: "تلاش دوباره",
  balance: "موجودی",
  points: "امتیاز",
  topup: "افزایش موجودی",
  demo: "نسخه نمایشی",
  txns: "تراکنش‌ها",
  txn: { topup: "افزایش موجودی", reward: "پاداش پیمان", penalty: "جریمه روز جاافتاده" } as Record<string, string>,
  rewards: "فروشگاه پاداش",
  reward: { gym20: "۲۰٪ تخفیف باشگاه", coach: "یک جلسه مشاوره تغذیه", bottle: "بطری آب ورزشی", charity: "کمک به خیریه سلامت" } as Record<string, string>,
  redeem: "دریافت",
  redeemed: "دریافت شد",
  atStake: "در گرو این هفته",
  members: "عضو",
  onTrack: "پیمان در مسیر",
  split: "تقسیم صندوق",
  winners: "برندگان",
  fee: "کارمزد خدمت",
  charity: "خیریه سلامت",
  charityNote: "اگر برنده‌ای نباشد، سهم برندگان به خیریه سلامت می‌رسد.",
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
    { name: "رایگان", price: "۰", f: ["یک پیمان فعال", "جدول جامعه", "سهم از صندوق"] },
    { name: "پریمیوم", price: "۱۴۹ هزار", f: ["پیمان‌های نامحدود", "گزارش کالری و درشت‌مغذی‌ها", "پیشنهاد غذای ایرانی", "کارمزد کمتر"] },
    { name: "سازمانی", price: "۹۰ تا ۱۸۰ هزار", f: ["پیش‌خوان سازمانی", "کارزار سلامت کارکنان", "گزارش مشارکت تجمیعی", "کوپن باشگاه‌های شریک"], per: "به ازای هر کارمند" },
  ],
  feeNote: (p: string) => `کارمزد خدمت ${p} از صندوق برداشته می‌شود؛ بقیه به برندگان یا خیریه سلامت می‌رسد.`,
};

type Dict = typeof fa;

const en: Dict = {
  brand: "FitPeyman",
  tagline: "Keep your word. Get paid.",
  nav: { today: "Today", pacts: "Pacts", wallet: "Wallet", community: "Community", business: "Business" },
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
  kcal: "kcal",
  foods: ["Ghormeh sabzi", "Koobideh kebab", "Adasi", "Shirazi salad", "Ash reshteh", "Omelette", "Joojeh kebab", "Bread, cheese & walnuts"],
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
  err: { exists: "You already have this pact", points: "Not enough points", settled: "This week is already closed", generic: "Something went wrong. Try again." },
  retry: "Try again",
  balance: "Balance",
  points: "Points",
  topup: "Add funds",
  demo: "Demo",
  txns: "Transactions",
  txn: { topup: "Top-up", reward: "Pact reward", penalty: "Missed-day penalty" },
  rewards: "Rewards",
  reward: { gym20: "20% off a gym pass", coach: "Nutrition coaching session", bottle: "Sports water bottle", charity: "Donate to a health charity" },
  redeem: "Redeem",
  redeemed: "Redeemed",
  atStake: "On the line this week",
  members: "members",
  onTrack: "pacts on track",
  split: "How the pool splits",
  winners: "Winners",
  fee: "Service fee",
  charity: "Health charity",
  charityNote: "If nobody wins, the winners' share goes to a health charity.",
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
    { name: "Free", price: "0", f: ["1 active pact", "Community board", "Share of the pool"] },
    { name: "Premium", price: "149k", f: ["Unlimited pacts", "Calorie & macro reports", "Iranian meal ideas", "Lower fee"] },
    { name: "Business", price: "90–180k", f: ["Company dashboard", "Employee wellness campaigns", "Aggregate participation reports", "Partner gym coupons"], per: "per employee" },
  ],
  feeNote: (p) => `A ${p} service fee comes out of the pool; the rest goes to winners or a health charity.`,
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
    document.cookie = `lang=${l};path=/;max-age=31536000`;
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
