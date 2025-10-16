class Utilities:
    start_marker = "====================="

    @staticmethod
    def trim_empty_lines(lines):
        """
        Trim trailing empty lines, then return the remaining lines
        in reverse order.

        If the marker '=====================' is found,
        return only lines after it (up to last non-empty line), reversed.

        If no marker is found, return everything from the beginning up to
        the last non-empty line, reversed.
        """
        # Step 1: Find the last non-empty line
        last_index = -1
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip() != "":
                last_index = i
                break

        if last_index == -1:
            return []  # All lines are empty

        # Step 2: Look for the marker from last_index backwards
        start_index = -1
        for i in range(last_index, -1, -1):
            if lines[i].strip() == Utilities.start_marker:
                start_index = i
                break

        # Step 3: Slice based on whether marker was found
        if start_index != -1:
            selected_lines = lines[start_index + 1:last_index + 1]
        else:
            selected_lines = lines[0:last_index + 1]

        # Step 4: Return in reverse order
        return selected_lines[::-1]
