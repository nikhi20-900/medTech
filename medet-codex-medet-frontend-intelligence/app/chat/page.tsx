"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  HeartPulse,
  Hospital,
  Languages,
  MapPin,
  Mic,
  MicOff,
  Navigation,
  Phone,
  Pill,
  Send,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  ClipboardList,
  Activity,
  ArrowUpRight,
  ChevronRight,
  ShieldAlert,
} from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/components/auth/AuthProvider";
import { AppShell, PageTransition } from "@/components/layout";
import { useLanguage } from "@/i18n/context";
import { Skeleton } from "@/components/ui/skeleton";
import {
  isEmergencyText,
  MedetCard,
  streamChatMessage,
  LocationPoint,
  HospitalPoint,
  getBrowserLocation,
  getNearbyHospitals,
} from "@/lib/api";

declare global {
  interface Window {
    SpeechRecognition: any;
    webkitSpeechRecognition: any;
  }
}

type ChatMessage = {
  id: number;
  role: "assistant" | "user";
  text: string;
  emergency?: boolean;
  cards?: MedetCard[];
  timestamp: string;
};

const quickActions = [
  { key: "chat.symptomCheck", prompt: "I have fever, cough, and body pain.", icon: Stethoscope },
  { key: "chat.medicineInfo", prompt: "Can you explain how to take my medicine safely?", icon: Pill },
  { key: "chat.firstAid", prompt: "What first aid should I do for a small cut?", icon: ShieldCheck },
  { key: "chat.nutrition", prompt: "Suggest simple nutrition tips for recovery.", icon: HeartPulse },
];

const sectionTitles = {
  en: {
    summary: "Summary",
    questions: "Follow-up Questions",
    selfCare: "Self-care Advice",
    warning: "Seek Medical Help If",
  },
  hi: {
    summary: "सारांश",
    questions: "फॉलो-अप प्रश्न",
    selfCare: "स्वयं-देखभाल सलाह",
    warning: "तुरंत डॉक्टर से मिलें यदि",
  },
  bn: {
    summary: "সারসংক্ষেপ",
    questions: "অনুসরণকারী প্রশ্ন",
    selfCare: "স্ব-যত্ন পরামর্শ",
    warning: "জরুরি চিকিৎসা নিন যদি",
  },
  ne: {
    summary: "सारांश",
    questions: "थप प्रश्नहरू",
    selfCare: "आत्म-हेरचाह सल्लाह",
    warning: "चिकित्सकीय मद्दत लिनुहोस् यदि",
  },
  ta: {
    summary: "சுருக்கம்",
    questions: "தொடர் கேள்விகள்",
    selfCare: "சுய-கவனிப்பு ஆலோசனை",
    warning: "மருத்துவ உதவி பெறவும்",
  },
  kn: {
    summary: "ಸಾರಾಂಶ",
    questions: "ಫಾಲೋ-ಅಪ್ ಪ್ರಶ್ನೆಗಳು",
    selfCare: "ಸ್ವಯಂ-ಆರೈಕೆ ಸಲಹೆ",
    warning: "ವೈದ್ಯಕೀಯ ಸಹಾಯ ಪಡೆಯಿರಿ",
  },
};

export interface ParsedResponse {
  summary: string;
  questions: string[];
  selfCare: string;
  warning: string;
}

export function parseAIResponse(text: string): ParsedResponse {
  const sections: ParsedResponse = {
    summary: "",
    questions: [],
    selfCare: "",
    warning: "",
  };

  if (!text) return sections;

  const lines = text.split("\n");
  let currentSection: "summary" | "questions" | "selfCare" | "warning" = "summary";

  const questionTriggers = [
    /follow-up question/i,
    /questions to help/i,
    /could you tell me/i,
    /please answer/i,
    /questions:/i,
    /follow up/i,
    /आगे की जानकारी/i,
    /অনুসরণকারী প্রশ্ন/i,
    /थप प्रश्नहरू/i,
    /தொடர் கேள்விகள்/i,
    /ಫಾಲೋ-ಅಪ್ ಪ್ರಶ್ನೆಗಳು/i
  ];
  
  const selfCareTriggers = [
    /self-care/i,
    /advice/i,
    /home remedies/i,
    /stay comfortable/i,
    /practical step/i,
    /स्वयं-देखभाल/i,
    /स्व-हेरचाह/i,
    /স্ব-যত্ন/i,
    /சுய-கவனிப்பு/i,
    /ಸ್ವಯಂ-ಆರೈಕೆ/i
  ];

  const warningTriggers = [
    /seek/i,
    /medical help/i,
    /warning sign/i,
    /emergency/i,
    /red flag/i,
    /danger/i,
    /worsen/i,
    /112/i,
    /आपात/i,
    /चेतावनी/i,
    /জরুরি/i,
    /সতর্ক/i,
    /आपतकालीन/i,
    /எச்சரிக்கை/i,
    /ತುರ್ತು/i,
    /ಎಚ್ಚರಿಕೆ/i
  ];

  for (let line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;

    // Detect section transitions
    let transitioned = false;
    
    if (warningTriggers.some(trigger => trigger.test(trimmed))) {
      currentSection = "warning";
      transitioned = true;
    }
    else if (questionTriggers.some(trigger => trigger.test(trimmed))) {
      currentSection = "questions";
      transitioned = true;
    }
    else if (selfCareTriggers.some(trigger => trigger.test(trimmed))) {
      currentSection = "selfCare";
      transitioned = true;
    }

    if (transitioned) {
      if (trimmed.startsWith("#") || trimmed.startsWith("*") || trimmed.endsWith(":")) {
        continue;
      }
    }

    // Append to current section
    if (currentSection === "summary") {
      sections.summary += (sections.summary ? "\n" : "") + trimmed;
    } else if (currentSection === "questions") {
      const cleanQuestion = trimmed.replace(/^[-*•\d+.\s?]+/, "").trim();
      if (cleanQuestion) {
        sections.questions.push(cleanQuestion);
      }
    } else if (currentSection === "selfCare") {
      sections.selfCare += (sections.selfCare ? "\n" : "") + trimmed;
    } else if (currentSection === "warning") {
      sections.warning += (sections.warning ? "\n" : "") + trimmed;
    }
  }

  return sections;
}

function formatMessageText(text: string) {
  if (!text) return "";
  // Bold formatting: **text**
  const boldRegex = /\*\*(.*?)\*\*/g;
  const parts = text.split("\n");
  
  return parts.map((line, idx) => {
    const trimmed = line.trim();
    if (!trimmed) return null;

    const renderText = (str: string) => {
      const subparts = [];
      let lastIndex = 0;
      let match;
      boldRegex.lastIndex = 0;
      
      while ((match = boldRegex.exec(str)) !== null) {
        if (match.index > lastIndex) {
          subparts.push(str.substring(lastIndex, match.index));
        }
        subparts.push(<strong key={match.index} className="font-extrabold text-slate-900 dark:text-white">{match[1]}</strong>);
        lastIndex = boldRegex.lastIndex;
      }
      if (lastIndex < str.length) {
        subparts.push(str.substring(lastIndex));
      }
      return subparts.length > 0 ? subparts : str;
    };

    if (trimmed.startsWith("-") || trimmed.startsWith("*") || trimmed.startsWith("•")) {
      return (
        <span key={idx} className="flex gap-2 items-start mt-1.5 pl-2 leading-relaxed">
          <span className="text-medet-primary shrink-0 mt-2 h-1.5 w-1.5 rounded-full bg-medet-primary/80" />
          <span className="text-slate-700 dark:text-slate-300 font-medium text-sm sm:text-base">{renderText(trimmed.substring(1).trim())}</span>
        </span>
      );
    }
    return (
      <p key={idx} className="mt-1 leading-relaxed text-slate-700 dark:text-slate-300 font-medium text-sm sm:text-base">
        {renderText(line)}
      </p>
    );
  });
}

function renderBackendCards(cards?: MedetCard[], messageId?: number) {
  if (!cards || !cards.length) return null;
  return (
    <div className="mt-4 space-y-2.5">
      {cards.slice(0, 3).map((card) => (
        <div
          key={`${messageId}-${card.type}-${card.title}`}
          className="rounded-2xl border border-slate-100 bg-white p-4 text-sm text-slate-700 shadow-sm flex items-start gap-3 hover:border-slate-200 hover:shadow-md transition-all duration-300"
        >
          <div className="mt-0.5 text-medet-primary p-1.5 rounded-xl bg-blue-50/50 shrink-0">
            <ShieldCheck className="h-4.5 w-4.5" />
          </div>
          <div>
            <p className="font-extrabold text-slate-800 text-sm sm:text-base">{card.title}</p>
            <p className="mt-1 text-slate-500 leading-relaxed text-xs sm:text-sm">{card.content}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

function AssistantResponse({ 
  text, 
  emergency, 
  cards, 
  id, 
  language 
}: { 
  text: string; 
  emergency?: boolean; 
  cards?: MedetCard[]; 
  id: number; 
  language: string 
}) {
  const parsed = useMemo(() => parseAIResponse(text), [text]);
  
  const hasMultipleSections = useMemo(() => {
    return parsed.questions.length > 0 || !!parsed.selfCare || !!parsed.warning;
  }, [parsed]);

  if (!hasMultipleSections) {
    return (
      <div className="space-y-3.5 w-full">
        <div className="space-y-1">
          {formatMessageText(text || "Thinking...")}
        </div>
        {renderBackendCards(cards, id)}
      </div>
    );
  }

  const titles = sectionTitles[language as keyof typeof sectionTitles] || sectionTitles.en;

  return (
    <div className="space-y-3 w-full">
      {/* 1. Summary Card */}
      {parsed.summary && (
        <motion.div 
          initial={{ opacity: 0, y: 4 }} 
          animate={{ opacity: 1, y: 0 }}
          className="p-3.5 rounded-r-2xl rounded-l-md border border-slate-100 border-l-4 border-l-blue-500 bg-blue-50/10 dark:bg-blue-950/5 flex gap-3 items-start"
        >
          <div className="p-1.5 rounded-lg bg-blue-100/40 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400 shrink-0">
            <Stethoscope className="h-4 w-4" />
          </div>
          <div className="space-y-0.5 flex-1 min-w-0">
            <h4 className="text-[10px] font-extrabold text-blue-900 dark:text-blue-300 tracking-wider uppercase flex items-center gap-1">
              <span>🩺</span> {titles.summary}
            </h4>
            <div className="space-y-0.5">
              {formatMessageText(parsed.summary)}
            </div>
          </div>
        </motion.div>
      )}

      {/* 2. Questions Card */}
      {parsed.questions.length > 0 && (
        <motion.div 
          initial={{ opacity: 0, y: 4 }} 
          animate={{ opacity: 1, y: 0 }}
          className="p-3.5 rounded-r-2xl rounded-l-md border border-slate-100 border-l-4 border-l-purple-500 bg-purple-50/10 dark:bg-purple-950/5 flex gap-3 items-start"
        >
          <div className="p-1.5 rounded-lg bg-purple-100/40 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400 shrink-0">
            <ClipboardList className="h-4 w-4" />
          </div>
          <div className="space-y-2 flex-1 min-w-0">
            <h4 className="text-[10px] font-extrabold text-purple-900 dark:text-purple-300 tracking-wider uppercase flex items-center gap-1">
              <span>❓</span> {titles.questions}
            </h4>
            <ul className="space-y-2">
              {parsed.questions.map((q, idx) => (
                <li key={idx} className="text-xs sm:text-sm text-purple-950/90 leading-relaxed font-semibold flex gap-2 items-start">
                  <span className="inline-flex items-center justify-center h-4.5 w-4.5 rounded bg-purple-100 text-purple-800 text-[10px] font-extrabold shrink-0 mt-0.5">
                    {idx + 1}
                  </span>
                  <span className="text-slate-700 dark:text-slate-300 font-medium">{q}</span>
                </li>
              ))}
            </ul>
          </div>
        </motion.div>
      )}

      {/* 3. Self-care Card */}
      {parsed.selfCare && (
        <motion.div 
          initial={{ opacity: 0, y: 4 }} 
          animate={{ opacity: 1, y: 0 }}
          className="p-3.5 rounded-r-2xl rounded-l-md border border-slate-100 border-l-4 border-l-emerald-500 bg-emerald-50/10 dark:bg-emerald-950/5 flex gap-3 items-start"
        >
          <div className="p-1.5 rounded-lg bg-emerald-100/40 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400 shrink-0">
            <HeartPulse className="h-4 w-4" />
          </div>
          <div className="space-y-0.5 flex-1 min-w-0">
            <h4 className="text-[10px] font-extrabold text-emerald-900 dark:text-emerald-300 tracking-wider uppercase flex items-center gap-1">
              <span>💊</span> {titles.selfCare}
            </h4>
            <div className="space-y-0.5">
              {formatMessageText(parsed.selfCare)}
            </div>
          </div>
        </motion.div>
      )}

      {/* 4. Warning Card */}
      {(parsed.warning || emergency) && (
        <motion.div 
          initial={{ opacity: 0, y: 4 }} 
          animate={{ opacity: 1, y: 0 }}
          className="p-3.5 rounded-r-2xl rounded-l-md border border-slate-100 border-l-4 border-l-red-500 bg-red-50/10 dark:bg-red-950/5 flex gap-3 items-start"
        >
          <div className="p-1.5 rounded-lg bg-red-100/40 text-red-600 dark:bg-red-900/30 dark:text-red-400 shrink-0">
            <AlertTriangle className="h-4 w-4 animate-pulse" />
          </div>
          <div className="space-y-0.5 flex-1 min-w-0">
            <h4 className="text-[10px] font-extrabold text-red-900 dark:text-red-300 tracking-wider uppercase flex items-center gap-1">
              <span>🚨</span> {titles.warning}
            </h4>
            <div className="space-y-0.5">
              {formatMessageText(parsed.warning || "Seek immediate medical help if symptoms get worse or if you experience chest pain, difficulty breathing, or severe bleeding.")}
            </div>
          </div>
        </motion.div>
      )}

      {renderBackendCards(cards, id)}
    </div>
  );
}

function EmergencyHospitals() {
  const { t } = useLanguage();
  const [location, setLocation] = useState<LocationPoint | null>(null);
  const [hospitals, setHospitals] = useState<HospitalPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getBrowserLocation()
      .then((loc) => {
        setLocation(loc);
        return getNearbyHospitals(loc);
      })
      .then((res) => {
        if (res.success) {
          setHospitals(res.hospitals.slice(0, 3)); // show top 3
        } else {
          setError("Could not retrieve nearby hospitals.");
        }
      })
      .catch((err) => {
        let msg = "Location unavailable";
        if (err.code === 1) {
          msg = "Location access denied. Please enable GPS.";
        }
        setError(msg);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  return (
    <div className="mt-4 p-4 rounded-2xl bg-red-50/50 border border-red-200/60 space-y-3 shadow-sm">
      <div className="flex items-center gap-2 text-base font-bold text-medet-emergency">
        <AlertTriangle className="h-5 w-5 animate-pulse text-red-600" />
        <span>Emergency: Nearest Hospitals</span>
      </div>

      <div className="flex flex-wrap gap-2">
        <a
          href="tel:112"
          className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl bg-medet-emergency px-4 text-sm font-bold text-white hover:bg-red-700 transition shadow-sm active:scale-95 duration-200"
        >
          <Phone className="h-4 w-4" />
          Call 112
        </a>
        <Link
          href="/nearby"
          className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl bg-white border border-slate-200 px-4 text-sm font-semibold text-medet-text hover:bg-slate-50 transition shadow-sm"
        >
          <MapPin className="h-4 w-4 text-medet-secondary" />
          View More Nearby
        </Link>
      </div>

      {loading ? (
        <div className="space-y-2">
          <Skeleton className="h-12 w-full rounded-xl" />
          <Skeleton className="h-12 w-full rounded-xl" />
        </div>
      ) : error ? (
        <p className="text-xs text-red-700 font-medium">{error}</p>
      ) : hospitals.length === 0 ? (
        <p className="text-xs text-slate-500">No hospitals found within 5 km.</p>
      ) : (
        <div className="space-y-2 mt-2">
          {hospitals.map((hospital) => (
            <div
              key={hospital.id}
              className="p-3.5 rounded-xl bg-white border border-red-100 flex flex-col justify-between sm:flex-row sm:items-center gap-3 shadow-xs hover:border-red-200/80 transition-all duration-300"
            >
              <div>
                <p className="font-extrabold text-slate-900 text-sm sm:text-base">{hospital.name}</p>
                <p className="text-xs text-slate-500 leading-relaxed mt-0.5 font-medium">{hospital.address}</p>
                <p className="text-xs font-bold text-medet-secondary mt-1 flex items-center gap-1">
                  <MapPin className="h-3 w-3" />
                  {hospital.distance_km.toFixed(1)} km away
                </p>
              </div>
              <div className="flex gap-2">
                <a
                  href="tel:112"
                  className="inline-flex h-8 items-center justify-center rounded-lg bg-medet-primary px-3 text-xs font-bold text-white hover:bg-blue-700 transition"
                >
                  Call
                </a>
                <a
                  href={`https://www.google.com/maps/search/?api=1&query=${hospital.latitude},${hospital.longitude}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex h-8 items-center justify-center rounded-lg bg-slate-100 px-3 text-xs font-bold text-medet-text hover:bg-slate-200 transition"
                >
                  Directions
                </a>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


export default function ChatPage() {
  const { t, language, languages } = useLanguage();
  const { session } = useAuth();
  const nextMessageId = useRef(2);
  const conversationId = useRef<string | undefined>(undefined);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [input, setInput] = useState(() => {
    if (typeof window === "undefined") return "";
    return new URLSearchParams(window.location.search).get("prompt") ?? "";
  });
  const [isListening, setIsListening] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    return [
      {
        id: 1,
        role: "assistant",
        text:
          "Hello, I am MEDET. Tell me what you are feeling in simple words. I will ask a few questions and help you decide what to do next.",
        timestamp: timeStr,
      },
    ];
  });

  const currentLanguage = useMemo(
    () => languages.find((item) => item.code === language),
    [language, languages]
  );

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

  async function sendMessage(text: string) {
    const cleanText = text.trim();
    if (!cleanText || isStreaming) return;

    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const userMessage: ChatMessage = {
      id: nextMessageId.current++,
      role: "user",
      text: cleanText,
      timestamp: timeStr,
    };

    const assistantId = nextMessageId.current++;
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: "assistant",
      text: "",
      emergency: isEmergencyText(cleanText),
      timestamp: timeStr,
    };

    setMessages((current) => [...current, userMessage, assistantMessage]);
    setInput("");
    setIsListening(false);
    setIsStreaming(true);

    try {
      for await (const chunk of streamChatMessage(cleanText, language, session, {
        conversationId: conversationId.current,
        onMetadata: (metadata) => {
          conversationId.current = metadata.conversationId;
          if (!metadata.medet) return;

          setMessages((current) =>
            current.map((message) =>
              message.id === assistantId
                ? {
                  ...message,
                  text: metadata.medet?.response || message.text,
                  emergency: Boolean(metadata.medet?.emergency),
                  cards: metadata.medet?.cards || [],
                }
                : message
            )
          );
        },
      })) {
        setMessages((current) =>
          current.map((message) =>
            message.id === assistantId
              ? { ...message, text: `${message.text}${chunk}` }
              : message
          )
        );
      }
    } finally {
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantId && !message.text.trim()
            ? {
              ...message,
              text:
                "I could not reach the healthcare service just now. Please try again, and call emergency services immediately if symptoms feel urgent.",
              emergency: true,
            }
            : message
        )
      );
      setIsStreaming(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    sendMessage(input);
  }

  return (
    <AppShell>
      <PageTransition>
        <div className="min-h-[calc(100vh-4rem)] bg-slate-50/50">
          <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-4 lg:grid lg:grid-cols-[minmax(0,1fr)_320px] lg:px-6">
            <section className="flex h-[calc(100dvh-8rem)] min-h-[580px] flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-md shadow-slate-100 lg:h-[calc(100vh-6.5rem)] lg:min-h-[620px]">
              
              {/* Top Banner / Header */}
              <div className="border-b border-slate-100 bg-white/95 px-5 py-3 sm:px-6">
                <div className="flex flex-col gap-2.5 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-50/70 border border-blue-100/30 shadow-xs">
                      <Bot className="h-5.5 w-5.5 text-medet-primary" />
                    </div>
                    <div>
                      <h1 className="text-lg sm:text-xl font-black text-slate-800 tracking-tight">{t("chat.welcomeTitle")}</h1>
                      <p className="text-[11px] sm:text-xs text-slate-400 font-bold mt-0.5">
                        Compassionate guidance in {currentLanguage?.nativeName}
                      </p>
                    </div>
                  </div>
                  <Link
                    href="/emergency"
                    className="inline-flex min-h-10 items-center justify-center gap-2 rounded-2xl bg-red-50 text-red-600 border border-red-100 px-4 text-xs font-extrabold shadow-xs hover:bg-red-100/80 active:scale-95 transition-all duration-200"
                  >
                    <AlertTriangle className="h-4 w-4 animate-pulse" />
                    {t("landing.emergencyHelp")}
                  </Link>
                </div>
              </div>

              {/* Chat Viewport */}
              <div className="flex-1 space-y-4 overflow-y-auto px-4 py-5 medet-scrollbar sm:px-5 bg-slate-50/30">
                <div className="rounded-2xl border border-amber-100 bg-amber-50/50 px-4 py-3 text-xs leading-relaxed text-amber-900/90 font-medium shadow-xs">
                  <span className="font-extrabold text-amber-950">Important: </span>
                  {t("chat.disclaimerText")}
                </div>

                <div className="space-y-4">
                  {messages.map((message) => {
                    const isUser = message.role === "user";
                    const isWelcome = message.id === 1 && message.role === "assistant";

                    if (isWelcome) {
                      return (
                        <motion.div
                          key={message.id}
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          className="rounded-2xl border border-slate-100 bg-white p-4 sm:p-5 shadow-sm max-w-xl mx-auto my-1.5 space-y-4"
                        >
                          <div className="flex items-start gap-3">
                            <div className="p-2 rounded-xl bg-blue-50 text-medet-primary shrink-0 border border-blue-100/30">
                              <HeartPulse className="h-5.5 w-5.5" />
                            </div>
                            <div>
                              <h2 className="text-lg font-black text-slate-800 leading-tight">
                                Welcome to MEDET
                              </h2>
                              <p className="mt-1 text-xs sm:text-sm text-slate-400 font-semibold leading-normal">
                                I&apos;ll ask a few medical questions to better understand your symptoms and guide you toward the appropriate next step.
                              </p>
                            </div>
                          </div>

                          <div className="grid grid-cols-2 gap-2.5 border-t border-b border-slate-100/80 py-3.5">
                            <div className="flex items-center gap-2 text-slate-700">
                              <Stethoscope className="h-4 w-4 text-medet-primary/80 shrink-0" />
                              <span className="text-xs font-extrabold text-slate-700">Symptom assessment</span>
                            </div>
                            
                            <div className="flex items-center gap-2 text-slate-700">
                              <AlertTriangle className="h-4 w-4 text-red-500 shrink-0" />
                              <span className="text-xs font-extrabold text-slate-700">Emergency check</span>
                            </div>

                            <div className="flex items-center gap-2 text-slate-700">
                              <ClipboardList className="h-4 w-4 text-purple-500 shrink-0" />
                              <span className="text-xs font-extrabold text-slate-700">Follow-up questions</span>
                            </div>

                            <div className="flex items-center gap-2 text-slate-700">
                              <ShieldCheck className="h-4 w-4 text-emerald-500 shrink-0" />
                              <span className="text-xs font-extrabold text-slate-700">Safe guidance</span>
                            </div>
                          </div>

                          <p className="text-[10px] text-slate-400 text-center leading-normal font-bold">
                            Not a replacement for a doctor. Always consult a real doctor for emergency symptoms.
                          </p>
                        </motion.div>
                      );
                    }

                    return (
                      <motion.div
                        key={message.id}
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.25 }}
                        className={`flex flex-col ${isUser ? "items-end" : "items-start"} space-y-1.5`}
                      >
                        <div
                          className={`max-w-[92%] sm:max-w-[82%] rounded-2xl px-4 py-3.5 text-sm sm:text-base leading-relaxed shadow-xs ${
                            isUser
                              ? "max-w-[85%] sm:max-w-[72%] rounded-br-none bg-medet-primary text-white font-medium shadow-sm shadow-blue-50/20 border-0"
                              : message.emergency
                              ? "rounded-tl-none border border-red-200/80 bg-red-50/50 text-red-950"
                              : "rounded-tl-none border border-slate-100 bg-white text-medet-text"
                          }`}
                        >
                          {!isUser && message.emergency && (
                            <div className="mb-3.5 flex items-center gap-2 text-sm font-extrabold text-medet-emergency uppercase tracking-wider">
                              <AlertTriangle className="h-4.5 w-4.5 animate-pulse text-red-600" />
                              {t("emergency.warningTitle")}
                            </div>
                          )}

                          {isUser ? (
                            <p className="leading-relaxed text-sm sm:text-base">{message.text}</p>
                          ) : (
                            <AssistantResponse 
                              text={message.text} 
                              emergency={message.emergency} 
                              cards={message.cards} 
                              id={message.id}
                              language={language}
                            />
                          )}

                          {!isUser && message.emergency && (
                            <EmergencyHospitals />
                          )}
                        </div>

                        {/* Timestamp under bubble */}
                        <span className="text-[9px] text-slate-400 font-bold px-1 select-none">
                          {message.timestamp}
                        </span>
                      </motion.div>
                    );
                  })}
                </div>

                <div ref={messagesEndRef} />

                {/* Bouncing Dots Loading Indicator */}
                {isStreaming && (
                  <div className="flex justify-start items-center gap-2 pl-2">
                    <div className="flex h-9 w-14 items-center justify-center rounded-2xl bg-white border border-slate-100 shadow-sm gap-1.5 animate-pulse">
                      <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce" style={{ animationDelay: '0ms' }}></span>
                      <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce" style={{ animationDelay: '150ms' }}></span>
                      <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce" style={{ animationDelay: '300ms' }}></span>
                    </div>
                    <span className="text-xs font-semibold text-slate-400">MEDET is typing...</span>
                  </div>
                )}
              </div>

              {/* Bottom Actions and Inputs */}
              <div className="border-t border-slate-100 bg-white p-4">
                
                {/* Redesigned Card-Style Quick Actions - Shrunk by 15% */}
                <div className="mb-3.5 flex gap-2.5 overflow-x-auto pb-1.5 -mx-4 px-4 sm:mx-0 sm:px-0 scrollbar-none">
                  {quickActions.map((action) => {
                    const Icon = action.icon;
                    return (
                      <button
                        key={action.key}
                        type="button"
                        onClick={() => sendMessage(action.prompt)}
                        disabled={isStreaming}
                        className="flex flex-col items-start p-3 rounded-xl border border-slate-100 bg-white hover:border-slate-200/80 shadow-xs hover:shadow hover:-translate-y-0.5 active:scale-95 disabled:opacity-50 disabled:pointer-events-none transition-all duration-300 w-[128px] shrink-0 text-left cursor-pointer"
                      >
                        <div className="p-2 rounded-lg bg-blue-50/50 text-medet-primary mb-2.5 shrink-0 border border-blue-100/20">
                          <Icon className="h-4 w-4" />
                        </div>
                        <span className="text-xs font-bold text-slate-800 leading-tight">
                          {t(action.key)}
                        </span>
                      </button>
                    );
                  })}
                </div>

                {/* Capsule Shape Form Input */}
                <form onSubmit={handleSubmit} className="relative flex items-end gap-2 bg-slate-50 hover:bg-slate-100/30 border border-slate-200 focus-within:border-medet-primary focus-within:bg-white focus-within:ring-2 focus-within:ring-blue-100/60 rounded-3xl p-1.5 transition-all duration-300 shadow-xs">
                  <button
                    type="button"
                    onClick={() => setIsListening((value) => !value)}
                    className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl transition-all duration-200 cursor-pointer ${isListening
                      ? "bg-medet-primary text-white animate-pulse"
                      : "text-slate-400 hover:bg-slate-200/50 hover:text-slate-700"
                      }`}
                    aria-label={t("chat.voiceInput")}
                    disabled={isStreaming}
                  >
                    {isListening ? <MicOff className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
                  </button>
                  
                  <textarea
                    id="chat-input"
                    value={input}
                    onChange={(event) => {
                      setInput(event.target.value);
                      event.target.style.height = "auto";
                      event.target.style.height = `${Math.min(event.target.scrollHeight, 140)}px`;
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        if (input.trim() && !isStreaming) {
                          sendMessage(input);
                        }
                      }
                    }}
                    rows={1}
                    placeholder={isListening ? t("chat.listening") : t("chat.placeholder")}
                    className="flex-1 min-h-[44px] max-h-36 resize-none bg-transparent px-3 py-2.5 text-base text-medet-text outline-none border-0 focus:ring-0 placeholder:text-slate-400 leading-relaxed font-semibold"
                    disabled={isStreaming}
                  />

                  <div className="flex flex-col items-center justify-center pr-1 select-none">
                    <span className="hidden md:inline text-[9px] text-slate-400 font-bold pb-1.5">
                      Enter to send
                    </span>
                    <button
                      type="submit"
                      className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-medet-primary text-white hover:bg-medet-primary-dark active:scale-95 shadow-sm hover:shadow transition-all duration-200 cursor-pointer disabled:opacity-40 disabled:pointer-events-none"
                      aria-label={t("chat.send")}
                      disabled={!input.trim() || isStreaming}
                    >
                      <Send className="h-4.5 w-4.5" />
                    </button>
                  </div>
                </form>

                <Link
                  href="/voice"
                  className="mt-3.5 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-2xl bg-medet-secondary-light/70 text-sm font-bold text-medet-secondary sm:hidden shadow-xs hover:bg-medet-secondary-light active:scale-95 transition-all"
                >
                  <Mic className="h-4 w-4" />
                  Open voice-first mode
                </Link>
              </div>
            </section>

            {/* Sidebar Poland */}
            <aside className="space-y-5">
              <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm hover:shadow transition-all duration-300">
                <div className="mb-4 flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-medet-secondary-light/60 border border-emerald-100/50 text-medet-secondary shrink-0">
                    <Languages className="h-5 w-5" />
                  </div>
                  <div>
                    <h2 className="font-extrabold text-slate-800 text-sm sm:text-base">{t("language.title")}</h2>
                    <p className="text-xs text-slate-400 font-bold mt-0.5">
                      {currentLanguage?.nativeName} selected
                    </p>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {languages.map((item) => (
                    <div
                      key={item.code}
                      className={`rounded-xl border px-3 py-2 text-xs font-bold text-center transition-all ${item.code === language
                        ? "border-medet-primary bg-blue-50/50 text-medet-primary"
                        : "border-slate-100 bg-slate-50 text-slate-500"
                        }`}
                    >
                      {item.nativeName}
                    </div>
                  ))}
                </div>
                <Link
                  href="/language"
                  className="mt-3.5 inline-flex min-h-11 w-full items-center justify-center rounded-2xl bg-slate-100 text-sm font-bold text-slate-600 hover:bg-slate-200 transition"
                >
                  Open language setup
                </Link>
              </div>

              <div className="rounded-3xl border border-emerald-100/70 bg-white p-5 shadow-sm hover:shadow transition-all duration-300">
                <h2 className="mb-3.5 font-extrabold text-slate-800 text-sm sm:text-base">How MEDET guides you</h2>
                <div className="space-y-3.5 text-xs sm:text-sm text-slate-500 font-semibold leading-relaxed">
                  {[
                    "Asks simple follow-up questions",
                    "Highlights emergency signs clearly",
                    "Recommends professional medical care",
                    "Keeps language and voice access visible",
                  ].map((item) => (
                    <div key={item} className="flex gap-2.5">
                      <CheckCircle2 className="mt-0.5 h-4.5 w-4.5 shrink-0 text-medet-secondary" />
                      <span>{item}</span>
                    </div>
                  ))}
                </div>
              </div>

              <Link
                href="/nearby"
                className="flex items-center justify-between rounded-3xl border border-slate-800 bg-slate-900 p-5 text-white shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-300"
              >
                <div>
                  <p className="text-xs text-white/70 font-bold uppercase tracking-wider">{t("nearby.title")}</p>
                  <h2 className="mt-1 font-extrabold text-base sm:text-lg">Find help close to you</h2>
                </div>
                <div className="p-3 bg-white/10 rounded-2xl text-emerald-300">
                  <MapPin className="h-6 w-6" />
                </div>
              </Link>

              <div className="rounded-3xl bg-gradient-to-br from-blue-600/90 to-emerald-600/95 p-6 text-white shadow-sm shadow-blue-50/50 hover:shadow-md transition-all duration-300">
                <Sparkles className="mb-3.5 h-6 w-6 text-yellow-300 animate-pulse" />
                <h2 className="font-extrabold text-base sm:text-lg">Built for low-bandwidth care</h2>
                <p className="mt-2 text-xs sm:text-sm leading-relaxed text-white/85 font-semibold">
                  Fast UI states, readable cards, and tap-friendly controls for low-end phones.
                </p>
              </div>
            </aside>
          </div>
        </div>
      </PageTransition>
    </AppShell>
  );
}
