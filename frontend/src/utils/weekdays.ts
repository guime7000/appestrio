import type { Weekday } from "@/api/types";

export const WEEKDAY_OPTIONS: { value: Weekday; label: string }[] = [
  { value: 1, label: "Lundi" },
  { value: 2, label: "Mardi" },
  { value: 3, label: "Mercredi" },
  { value: 4, label: "Jeudi" },
  { value: 5, label: "Vendredi" },
  { value: 6, label: "Samedi" },
  { value: 7, label: "Dimanche" },
];

export function weekdayLabels(weekdays: Weekday[]): string {
  if (weekdays.length === 0) return "—";
  return WEEKDAY_OPTIONS.filter((option) => weekdays.includes(option.value))
    .map((option) => option.label)
    .join(", ");
}
