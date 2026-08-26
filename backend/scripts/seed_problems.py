"""
Run inside the api container (it has the app package + deps):

    docker compose exec api python -m scripts.seed_problems

Creates an admin user (admin / admin12345 — change immediately in anything
beyond local dev) and three sample problems so you have something to submit
against right after `docker compose up`.
"""

import asyncio

from sqlalchemy import select

from app.database import AsyncSessionLocal, Base, engine
from app.models import Difficulty, Problem, TestCase, User
from app.security import hash_password

PROBLEMS = [
    {
        "slug": "two-sum",
        "title": "Two Sum",
        "statement": (
            "Given a line of space-separated integers followed by a target on the next line, "
            "print the 0-indexed positions of the two numbers that add up to the target, "
            "space-separated, in increasing order. Exactly one solution exists."
        ),
        "difficulty": Difficulty.EASY,
        "time_limit_seconds": 2.0,
        "memory_limit_mb": 128,
        "tests": [
            ("2 7 11 15\n9", "0 1", True),
            ("3 2 4\n6", "1 2", True),
            ("3 3\n6", "0 1", False),
            ("1 5 3 8 2 9 -4 7\n5", "2 4", False),
        ],
    },
    {
        "slug": "reverse-string",
        "title": "Reverse a String",
        "statement": "Read a single line of text and print it reversed.",
        "difficulty": Difficulty.EASY,
        "time_limit_seconds": 1.0,
        "memory_limit_mb": 64,
        "tests": [
            ("hello", "olleh", True),
            ("racecar", "racecar", True),
            ("Codearena", "aneraedoC", False),
        ],
    },
    {
        "slug": "fibonacci-mod",
        "title": "Fibonacci mod 1e9+7",
        "statement": (
            "Given n (0 <= n <= 5,000,000) on a single line, print the n-th Fibonacci number "
            "modulo 1,000,000,007 (F(0)=0, F(1)=1). Designed to punish O(n) solutions with a "
            "slow per-step constant factor under the time limit — this is the TLE tripwire problem."
        ),
        "difficulty": Difficulty.MEDIUM,
        "time_limit_seconds": 2.0,
        "memory_limit_mb": 128,
        "tests": [
            ("10", "55", True),
            ("0", "0", True),
            ("100000", "911435502", False),
        ],
    },
    {
        "slug": "palindrome-check",
        "title": "Palindrome Check",
        "statement": (
            "Read a single line string s. Print YES if s reads the same forwards and backwards "
            "(case-sensitive, no trimming of internal characters), otherwise print NO."
        ),
        "difficulty": Difficulty.EASY,
        "time_limit_seconds": 1.0,
        "memory_limit_mb": 64,
        "tests": [
            ("racecar", "YES", True),
            ("hello", "NO", True),
            ("madam", "YES", False),
        ],
    },
    {
        "slug": "valid-parentheses",
        "title": "Valid Parentheses",
        "statement": (
            "Read a single line containing only the characters ( ) [ ] { }. Print YES if every "
            "bracket is closed in the correct order, otherwise print NO."
        ),
        "difficulty": Difficulty.EASY,
        "time_limit_seconds": 1.0,
        "memory_limit_mb": 64,
        "tests": [
            ("([]{})", "YES", True),
            ("([)]", "NO", True),
            ("(((", "NO", False),
        ],
    },
    {
        "slug": "binary-search",
        "title": "Binary Search",
        "statement": (
            "Line 1: a strictly increasing, space-separated list of integers. Line 2: a target "
            "integer. Print the 0-indexed position of the target in the list, or -1 if it is not "
            "present. An O(n) scan will pass small cases but is not what this problem is testing — "
            "write it as an actual binary search."
        ),
        "difficulty": Difficulty.EASY,
        "time_limit_seconds": 1.0,
        "memory_limit_mb": 64,
        "tests": [
            ("1 3 5 7 9 11\n7", "3", True),
            ("2 4 6 8\n5", "-1", True),
            ("1 2 3 4 5 6 7 8 9 10\n1", "0", False),
        ],
    },
    {
        "slug": "count-vowels",
        "title": "Count Vowels",
        "statement": "Read a single line of text and print how many of its characters are vowels (a, e, i, o, u), counting both upper- and lower-case.",
        "difficulty": Difficulty.EASY,
        "time_limit_seconds": 1.0,
        "memory_limit_mb": 64,
        "tests": [
            ("Hello World", "3", True),
            ("xyz", "0", True),
            ("AEIOUaeiou", "10", False),
        ],
    },
    {
        "slug": "fizzbuzz",
        "title": "FizzBuzz",
        "statement": (
            "Read an integer n. Print the numbers from 1 to n, one per line: for multiples of 3 "
            "print Fizz, for multiples of 5 print Buzz, for multiples of both print FizzBuzz, "
            "otherwise print the number itself."
        ),
        "difficulty": Difficulty.EASY,
        "time_limit_seconds": 1.0,
        "memory_limit_mb": 64,
        "tests": [
            ("15", "1\n2\nFizz\n4\nBuzz\nFizz\n7\n8\nFizz\nBuzz\n11\nFizz\n13\n14\nFizzBuzz", True),
            ("3", "1\n2\nFizz", True),
            ("5", "1\n2\nFizz\n4\nBuzz", False),
        ],
    },
    {
        "slug": "second-largest",
        "title": "Second Largest Element",
        "statement": (
            "Read a single line of space-separated integers. Print the second largest distinct "
            "value in the list. There are always at least two distinct values."
        ),
        "difficulty": Difficulty.EASY,
        "time_limit_seconds": 1.0,
        "memory_limit_mb": 64,
        "tests": [
            ("10 20 4 45 99", "45", True),
            ("5 5 5 9 1", "5", True),
            ("1 2", "1", False),
        ],
    },
    {
        "slug": "gcd-lcm",
        "title": "GCD and LCM",
        "statement": (
            "Read two space-separated positive integers a and b on a single line. Print their "
            "GCD and LCM, space-separated, on one line, in that order."
        ),
        "difficulty": Difficulty.EASY,
        "time_limit_seconds": 1.0,
        "memory_limit_mb": 64,
        "tests": [
            ("12 18", "6 36", True),
            ("7 13", "1 91", True),
            ("100 75", "25 300", False),
        ],
    },
    {
        "slug": "run-length-encoding",
        "title": "Run-Length Encoding",
        "statement": (
            "Read a single line string of letters and print its run-length encoding: each maximal "
            "run of a repeated character becomes that character followed by the run's length "
            "(e.g. aaabbbccd -> a3b3c2d1)."
        ),
        "difficulty": Difficulty.EASY,
        "time_limit_seconds": 1.0,
        "memory_limit_mb": 64,
        "tests": [
            ("aaabbbccd", "a3b3c2d1", True),
            ("abcd", "a1b1c1d1", True),
            ("wwwwaaadexxxxxx", "w4a3d1e1x6", False),
        ],
    },
    {
        "slug": "anagram-check",
        "title": "Anagram Check",
        "statement": (
            "Read two lines, each a lowercase word. Print YES if the second word is an anagram of "
            "the first (same letters, same multiplicity, any order), otherwise print NO."
        ),
        "difficulty": Difficulty.MEDIUM,
        "time_limit_seconds": 1.0,
        "memory_limit_mb": 64,
        "tests": [
            ("listen\nsilent", "YES", True),
            ("hello\nworld", "NO", True),
            ("dormitory\ndirtyroom", "YES", False),
        ],
    },
    {
        "slug": "matrix-transpose",
        "title": "Matrix Transpose",
        "statement": (
            "Line 1: two integers r and c. The next r lines each contain c space-separated "
            "integers, the matrix. Print its transpose: c lines of r space-separated integers."
        ),
        "difficulty": Difficulty.MEDIUM,
        "time_limit_seconds": 1.0,
        "memory_limit_mb": 64,
        "tests": [
            ("2 3\n1 2 3\n4 5 6", "1 4\n2 5\n3 6", True),
            ("1 1\n7", "7", True),
            ("3 1\n1\n2\n3", "1 2 3", False),
        ],
    },
    {
        "slug": "longest-common-prefix",
        "title": "Longest Common Prefix",
        "statement": (
            "Line 1: an integer n. The next n lines each contain one lowercase word. Print the "
            "longest string that is a prefix of every word. Print an empty line if there is none."
        ),
        "difficulty": Difficulty.MEDIUM,
        "time_limit_seconds": 1.0,
        "memory_limit_mb": 64,
        "tests": [
            ("3\nflower\nflow\nflight", "fl", True),
            ("3\ndog\nracecar\ncar", "", True),
            ("3\ninterspecies\ninterstellar\ninterstate", "inters", False),
        ],
    },
    {
        "slug": "max-subarray-sum",
        "title": "Maximum Subarray Sum",
        "statement": (
            "Read a single line of space-separated integers (may be negative). Print the maximum "
            "possible sum of a contiguous, non-empty subarray. Aim for O(n) — Kadane's algorithm."
        ),
        "difficulty": Difficulty.MEDIUM,
        "time_limit_seconds": 1.0,
        "memory_limit_mb": 64,
        "tests": [
            ("-2 1 -3 4 -1 2 1 -5 4", "6", True),
            ("1", "1", True),
            ("5 4 -1 7 8", "23", False),
        ],
    },
    {
        "slug": "word-frequency",
        "title": "Most Frequent Word",
        "statement": (
            "Read a single line of space-separated words. Print the most frequent word, "
            "lower-cased. If there is a tie, print the lexicographically smallest of the tied "
            "words."
        ),
        "difficulty": Difficulty.MEDIUM,
        "time_limit_seconds": 1.0,
        "memory_limit_mb": 64,
        "tests": [
            ("the quick brown fox the lazy the dog", "the", True),
            ("a b b c c", "b", True),
            ("one", "one", False),
        ],
    },
    {
        "slug": "prime-count",
        "title": "Count Primes Below N",
        "statement": (
            "Read an integer n (0 <= n <= 2,000,000). Print how many primes are strictly less "
            "than n. This is the sieve tripwire problem — a trial-division-per-number approach "
            "will time out at the upper end; use a Sieve of Eratosthenes."
        ),
        "difficulty": Difficulty.HARD,
        "time_limit_seconds": 2.0,
        "memory_limit_mb": 256,
        "tests": [
            ("30", "10", True),
            ("2", "0", True),
            ("1000000", "78498", False),
        ],
    },
    {
        "slug": "merge-intervals",
        "title": "Merge Overlapping Intervals",
        "statement": (
            "Line 1: an integer n. Each of the next n lines has two integers start end. Merge all "
            "overlapping intervals and print the merged intervals, one per line as 'start end', "
            "sorted by start."
        ),
        "difficulty": Difficulty.HARD,
        "time_limit_seconds": 1.5,
        "memory_limit_mb": 128,
        "tests": [
            ("4\n1 3\n2 6\n8 10\n15 18", "1 6\n8 10\n15 18", True),
            ("2\n1 4\n4 5", "1 5", True),
            ("1\n5 5", "5 5", False),
        ],
    },
]


async def seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.username == "admin"))
        if result.scalar_one_or_none() is None:
            db.add(
                User(
                    username="admin",
                    email="admin@codearena.local",
                    hashed_password=hash_password("admin12345"),
                    is_admin=True,
                )
            )
            await db.commit()
            print("Created admin user: admin / admin12345")
        else:
            print("Admin user already exists, skipping")

        for spec in PROBLEMS:
            result = await db.execute(select(Problem).where(Problem.slug == spec["slug"]))
            if result.scalar_one_or_none() is not None:
                print(f"Problem '{spec['slug']}' already exists, skipping")
                continue

            problem = Problem(
                slug=spec["slug"],
                title=spec["title"],
                statement=spec["statement"],
                difficulty=spec["difficulty"],
                time_limit_seconds=spec["time_limit_seconds"],
                memory_limit_mb=spec["memory_limit_mb"],
            )
            problem.test_cases = [
                TestCase(ordinal=i, input_data=inp, expected_output=out, is_sample=sample, weight=1)
                for i, (inp, out, sample) in enumerate(spec["tests"])
            ]
            db.add(problem)
            print(f"Created problem '{spec['slug']}' with {len(spec['tests'])} test cases")

        await db.commit()


if __name__ == "__main__":
    asyncio.run(seed())
