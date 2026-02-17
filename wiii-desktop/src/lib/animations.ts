/**
 * Shared animation presets — Sprint 104: "Sống Động" UX.
 *
 * Uses `motion` (framer-motion successor) for hardware-accelerated animations.
 * All presets are consistent across components for a cohesive feel.
 */

import type { Variants } from "motion/react";

/** Message entry — slide up + fade in */
export const messageEntry: Variants = {
  hidden: { opacity: 0, y: 12 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.25, ease: "easeOut" },
  },
};

/** User message — slide from right */
export const userMessageEntry: Variants = {
  hidden: { opacity: 0, x: 16 },
  visible: {
    opacity: 1,
    x: 0,
    transition: { duration: 0.25, ease: "easeOut" },
  },
};

/** AI message — slide from left */
export const aiMessageEntry: Variants = {
  hidden: { opacity: 0, x: -16 },
  visible: {
    opacity: 1,
    x: 0,
    transition: { duration: 0.25, ease: "easeOut" },
  },
};

/** Simple fade in */
export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { duration: 0.2 },
  },
};

/** Slide down expand — for pipeline steps, collapsible content */
export const slideDown: Variants = {
  hidden: { opacity: 0, height: 0 },
  visible: {
    opacity: 1,
    height: "auto",
    transition: { duration: 0.2, ease: "easeOut" },
  },
  exit: {
    opacity: 0,
    height: 0,
    transition: { duration: 0.15 },
  },
};

/** Stagger container — children appear with delay */
export const staggerContainer: Variants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.05 },
  },
};

/** Stagger item — used with staggerContainer */
export const staggerItem: Variants = {
  hidden: { opacity: 0, y: 8 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.2, ease: "easeOut" },
  },
};

/** Pipeline step entry — slide down with stagger */
export const stepEntry: Variants = {
  hidden: { opacity: 0, y: -4 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.2, ease: "easeOut" },
  },
};

/** Pipeline stagger — 100ms between steps */
export const stepStagger: Variants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.1 },
  },
};

/** Checkmark scale spring */
export const checkmarkPop: Variants = {
  hidden: { scale: 0 },
  visible: {
    scale: 1,
    transition: { type: "spring", stiffness: 400, damping: 15 },
  },
};

/** Sidebar item — slide in from left for new items */
export const sidebarItemEntry: Variants = {
  hidden: { opacity: 0, x: -20 },
  visible: {
    opacity: 1,
    x: 0,
    transition: { duration: 0.2, ease: "easeOut" },
  },
  exit: {
    opacity: 0,
    x: -20,
    transition: { duration: 0.15 },
  },
};

/** Pill suggestion entry — fade + rise */
export const pillEntry: Variants = {
  hidden: { opacity: 0, y: 6, scale: 0.95 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.2, ease: "easeOut" },
  },
};

/** Pill stagger — 50ms between pills */
export const pillStagger: Variants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.05 },
  },
};

/** Slide up from bottom — for panels, banners */
export const slideUp: Variants = {
  hidden: { opacity: 0, y: 16 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.2, ease: "easeOut" },
  },
  exit: {
    opacity: 0,
    y: 16,
    transition: { duration: 0.15 },
  },
};

/** Slide in from right — for side panels */
export const slideInRight: Variants = {
  hidden: { opacity: 0, x: 320 },
  visible: {
    opacity: 1,
    x: 0,
    transition: { duration: 0.25, ease: "easeOut" },
  },
  exit: {
    opacity: 0,
    x: 320,
    transition: { duration: 0.2, ease: "easeIn" },
  },
};
