#ifndef CENTROID_UTILS_H
#define CENTROID_UTILS_H

#ifdef __cplusplus
#endif

#include <stdbool.h>
#include <vector>

typedef struct {
    float x;
    float y;
} Point;

typedef struct {
    Point point1;
    Point point2;
    bool valid;
} IntersectionPoints;

/**
 * @brief Calculate the intersection points of two circles.
 * 
 * @param p1 Pointer to the center of the first circle.
 * @param p2 Pointer to the center of the second circle.
 * @param r1 Radius of the first circle.
 * @param r2 Radius of the second circle.
 * @return IntersectionPoints struct containing two points and a validity flag.
 */
IntersectionPoints calculateIntersections(Point* p1, Point* p2, float r1, float r2);

/**
 * @brief Select the intersection point that lies within a given radius of a third point.
 * 
 * @param intersection Struct containing two possible intersection points.
 * @param p Pointer to the third point.
 * @param r Radius around point p to check for validity.
 * @return Point struct representing the selected valid intersection.
 */
Point selectIntersection(IntersectionPoints intersection, Point* p, float r);

/**
 * @brief Calculate the centroid of the intersection of two circles.
 * 
 * @param p1 Pointer to the center of the first circle.
 * @param p2 Pointer to the center of the second circle.
 * @param r1 Radius of the first circle.
 * @param r2 Radius of the second circle.
 * @return Point struct representing the centroid.
 */
Point calculateCentroid2Circles(Point* p1, Point* p2, float r1, float r2);

/**
 * @brief Calculate the weighted centroid using intersections between three circles.
 * 
 * @param p1 Pointer to the center of the first circle.
 * @param p2 Pointer to the center of the second circle.
 * @param p3 Pointer to the center of the third circle.
 * @param r1 Radius of the first circle.
 * @param r2 Radius of the second circle.
 * @param r3 Radius of the third circle.
 * @return Point struct representing the weighted centroid.
 */
Point calculateWeightedCentroid(Point* p1, Point* p2, Point* p3,IntersectionPoints p12, IntersectionPoints p13, IntersectionPoints p23, float r1, float r2, float r3);

std::vector<Point> getBeaconPositions(Point* p1, Point* p2, Point* p3, float r1, float r2, float r3);

#ifdef __cplusplus
#endif

#endif // CENTROID_UTILS_H
