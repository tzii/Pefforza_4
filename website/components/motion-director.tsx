'use client';

import { useEffect, useState, useSyncExternalStore } from 'react';
import { Pause, Play } from 'lucide-react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

const subscribeMotion = (notify: () => void) => {
  const preference = matchMedia('(prefers-reduced-motion: reduce)');
  preference.addEventListener('change', notify);
  return () => preference.removeEventListener('change', notify);
};
const motionSnapshot = () =>
  matchMedia('(prefers-reduced-motion: reduce)').matches;
const serverMotionSnapshot = () => true;

export function MotionDirector() {
  const reduced = useSyncExternalStore(
    subscribeMotion,
    motionSnapshot,
    serverMotionSnapshot,
  );
  const [override, setOverride] = useState<boolean | null>(null);
  const paused = override ?? reduced;

  useEffect(() => {
    document.documentElement.dataset.motion = paused ? 'off' : 'on';
    if (paused) return;
    const media = gsap.matchMedia();
    const context = gsap.context(() => {
      gsap.from('.hero-copy h1 > span', {
        y: 70,
        opacity: 0,
        rotation: 2,
        duration: 1.2,
        stagger: 0.13,
        ease: 'power4.out',
        clearProps: 'all',
      });
      gsap.from('.hero-copy > p, .hero-actions, .hero-topline', {
        y: 18,
        opacity: 0,
        duration: 0.9,
        stagger: 0.12,
        delay: 0.3,
        clearProps: 'all',
      });
      gsap.from('.hero-art img', {
        scale: 1.08,
        opacity: 0,
        duration: 1.7,
        ease: 'power2.out',
        clearProps: 'all',
      });
      gsap.to('.reading-progress', {
        scaleX: 1,
        ease: 'none',
        scrollTrigger: {
          trigger: 'main',
          start: 'top top',
          end: 'bottom bottom',
          scrub: true,
        },
      });
      gsap.to('.hero-art', {
        yPercent: 15,
        rotate: 4,
        ease: 'none',
        scrollTrigger: {
          trigger: '.hero',
          start: 'top top',
          end: 'bottom top',
          scrub: 1,
        },
      });
      gsap.to('.hero-copy', {
        y: -60,
        opacity: 0.25,
        ease: 'none',
        scrollTrigger: {
          trigger: '.hero',
          start: '30% top',
          end: 'bottom top',
          scrub: 1,
        },
      });
      gsap.from('.intro-title', {
        y: 65,
        opacity: 0.15,
        duration: 1,
        scrollTrigger: {
          trigger: '.intro-title',
          start: 'top 92%',
          end: 'top 48%',
          scrub: 1,
        },
      });
      gsap.to('.large-asterisk', {
        rotation: 160,
        ease: 'none',
        scrollTrigger: {
          trigger: '.intro',
          start: 'top bottom',
          end: 'bottom top',
          scrub: 1,
        },
      });
      gsap.utils
        .toArray<HTMLElement>(
          '.play-copy, .game-shell, .launch-heading, .launch-tabs',
        )
        .forEach((el) =>
          gsap.from(el, {
            y: 45,
            opacity: 0,
            duration: 0.85,
            ease: 'power3.out',
            scrollTrigger: { trigger: el, start: 'top 94%', once: true },
          }),
        );
      gsap.from('.footer-wordmark', {
        yPercent: 38,
        rotation: 3,
        opacity: 0.25,
        ease: 'none',
        scrollTrigger: {
          trigger: '.site-footer',
          start: 'top bottom',
          end: 'bottom bottom',
          scrub: 1,
        },
      });
      gsap.to('.footer-star', {
        rotation: 120,
        ease: 'none',
        scrollTrigger: {
          trigger: '.site-footer',
          start: 'top bottom',
          end: 'bottom bottom',
          scrub: 1,
        },
      });
      media.add('(min-width: 1001px)', () => {
        const track = document.querySelector<HTMLElement>('.story-track');
        if (!track) return;
        const timeline = gsap.timeline({
          scrollTrigger: {
            trigger: '.story-stage',
            start: 'top top',
            end: () => `+=${window.innerWidth * 2.2}`,
            pin: true,
            scrub: 1,
            anticipatePin: 1,
            refreshPriority: 1,
            invalidateOnRefresh: true,
          },
        });
        timeline.to(
          track,
          {
            x: () => -(track.scrollWidth - window.innerWidth),
            ease: 'none',
            duration: 1,
          },
          0,
        );
        timeline.to(
          '.story-progress > span',
          { scaleX: 1, ease: 'none', duration: 1 },
          0,
        );
      });
    });
    let disposed = false;
    void document.fonts.ready.then(() => {
      if (!disposed) ScrollTrigger.refresh();
    });
    return () => {
      disposed = true;
      media.revert();
      context.revert();
      delete document.documentElement.dataset.motion;
    };
  }, [paused]);

  return (
    <>
      <div className="reading-progress" aria-hidden="true" />
      <button
        className="motion-toggle"
        onClick={() => setOverride(!paused)}
        aria-pressed={!paused}
        aria-label={paused ? 'Enable animations' : 'Pause animations'}
      >
        {paused ? <Play size={12} /> : <Pause size={12} />}
        <span>Motion {paused ? 'off' : 'on'}</span>
      </button>
    </>
  );
}
