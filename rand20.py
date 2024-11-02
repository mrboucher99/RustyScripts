#!/usr/bin/env python3

###################################
#          RAND20 SCRIPT          #
# Randomly rolls 1-20 until 20    #
# Tracks frequency of each number #
# Created by Matthew Boucher      #
# 2024-11-02                      #
###################################

import random

def main():
    # Initialize a dictionary to track counts of each roll from 1 to 20
    roll_counts = {i: 0 for i in range(1, 21)}
    roll_total = 0  # Track total rolls

    # Loop until we roll a 20
    while True:
        roll = random.randint(1, 20)  # Randomly select a number between 1 and 20
        roll_counts[roll] += 1        # Update the count for this roll
        roll_total += 1               # Increment total roll count
        
        # Stop if we rolled a 20
        if roll == 20:
            break

    # Display the roll counts and total roll count
    print("Roll counts for each number:")
    for number, count in roll_counts.items():
        print(f"Number {number}: {count} times")

    print(f"\nTotal rolls to get a 20: {roll_total}")

if __name__ == "__main__":
    main()
